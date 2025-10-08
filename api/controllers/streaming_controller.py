"""
Streaming Controller - WebSocket endpoint for real-time transcription.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Optional

from api.services.transcriber_service import Transcriber, FasterWhisperTranscriber
from api.services.streaming_service import StreamingService, StreamingSession
from api.config.settings import settings
from api.config.logging import get_logger

logger = get_logger("controller.streaming")
router = APIRouter()


def get_transcriber() -> Transcriber:
    """Dependency: Get transcriber instance."""
    return FasterWhisperTranscriber(compute_type=settings.compute_type)


def get_streaming_service(transcriber: Transcriber = Depends(get_transcriber)) -> StreamingService:
    """Dependency: Get streaming service instance."""
    return StreamingService(transcriber)


@router.websocket("/ws/transcribe")
async def ws_transcribe(
    websocket: WebSocket,
    service: StreamingService = Depends(get_streaming_service)
):
    """
    WebSocket endpoint for real-time audio transcription.
    
    Protocol:
    1. Client connects
    2. Client sends handshake: {"type": "start", "format": "s16le", "rate": 16000}
    3. Client streams audio data (binary)
    4. Server sends transcription deltas: {"type": "delta", "append": "text", "segments": [...]}
    5. Client sends "stop" or "close" (text)
    6. Server sends final: {"type": "final"}
    
    Args:
        websocket: WebSocket connection
        service: Streaming service (injected)
    """
    await websocket.accept()
    
    session_id = id(websocket)
    logger.info(f"Client connected [id={session_id}]")
    
    session: Optional[StreamingSession] = None
    
    try:
        # Step 1: Receive and parse handshake
        handshake_msg = await websocket.receive_text()
        
        try:
            audio_format, model_size_override = service.parse_handshake(
                handshake_msg,
                websocket.query_params.get("model_size")
            )
            logger.info(f"Handshake received [id={session_id}]: format={audio_format.format_type}, rate={audio_format.sample_rate}")
        except ValueError as e:
            logger.warning(f"Invalid handshake [id={session_id}]: {e}")
            await websocket.close(code=1002, reason="Invalid handshake")
            return
        
        # Step 2: Create session
        session = service.create_session(session_id, audio_format, model_size_override)
        
        # Step 3: Start FFmpeg if needed
        if audio_format.needs_conversion():
            await session.start_ffmpeg_decoder()
        else:
            logger.info(f"Direct PCM mode [id={session_id}]: no conversion needed")
        
        # Step 4: Process audio stream
        while True:
            try:
                msg = await websocket.receive()
                
                # Handle text messages (stop/close)
                if "text" in msg:
                    if msg["text"] in {"stop", "close"}:
                        logger.info(f"Stop signal received [id={session_id}]")
                        
                        # Close FFmpeg input if needed
                        if audio_format.needs_conversion():
                            await session.close_ffmpeg_input()
                        
                        # Wait for final data
                        await asyncio.sleep(0.15)
                        
                        # Force final transcription
                        result = await service.process_audio_chunk(session, b"", force=True)
                        if result:
                            await websocket.send_json(result)
                        
                        # Send final message
                        await websocket.send_json({"type": "final"})
                        logger.info(f"Session finalized [id={session_id}]")
                        break
                    continue
                
                # Handle binary messages (audio data)
                if "bytes" not in msg or not msg["bytes"]:
                    continue
                
                data_bytes = msg["bytes"]
                
                # Process audio chunk
                result = await service.process_audio_chunk(session, data_bytes)
                
                # Send transcription if available
                if result:
                    await websocket.send_json(result)
            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected [id={session_id}]")
                break
            
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    logger.info(f"Client disconnected (runtime) [id={session_id}]")
                    break
                logger.error(f"Runtime error [id={session_id}]: {e}")
                raise
    
    except Exception as e:
        logger.error(f"Unexpected error [id={session_id}]: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
    
    finally:
        # Cleanup session resources
        if session:
            await session.cleanup()
