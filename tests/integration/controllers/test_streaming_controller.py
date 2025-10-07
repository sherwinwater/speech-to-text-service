"""
Tests for streaming controller (WebSocket endpoints).
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.controllers.streaming_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber


# Override dependency
@pytest.fixture
def client():
    """Create test client with mocked transcriber."""
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestStreamingController:
    """Test WebSocket streaming endpoints."""
    
    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment."""
        # TODO: Implement test
        pass
    
    def test_websocket_handshake(self, client):
        """Test WebSocket handshake protocol."""
        # TODO: Implement test
        pass
    
    def test_websocket_invalid_handshake(self, client):
        """Test WebSocket with invalid handshake."""
        # TODO: Implement test
        pass
    
    def test_websocket_audio_streaming(self, client):
        """Test audio streaming over WebSocket."""
        # TODO: Implement test
        pass
    
    def test_websocket_stop_signal(self, client):
        """Test WebSocket stop signal."""
        # TODO: Implement test
        pass
    
    def test_websocket_disconnect(self, client):
        """Test WebSocket disconnection."""
        # TODO: Implement test
        pass
