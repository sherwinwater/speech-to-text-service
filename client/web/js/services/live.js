import { WS_URL, withModelSize } from '../config/config.js';
import { getModelSize } from '../components/modelSelector.js';

/**
 * Initialize live mode functionality
 */
export function initLive() {
    const liveBtn = document.getElementById('live');
    const stopBtn = document.getElementById('stopLive');
    const outLive = document.getElementById('out-live');
    const liveStatus = document.getElementById('liveStatus');
    const liveHelp = document.getElementById('liveHelp');

    let ws, audioCtx, pcmNode, liveStream;
    const supportsMediaRecorder = 'MediaRecorder' in window;
    let transcript = "";
    let isLiveActive = false;

    function setLiveEnabled(active) {
        isLiveActive = active;
        liveBtn.disabled = active;
        stopBtn.disabled = !active;
    }

    liveBtn.onclick = async () => {
        transcript = "";
        outLive.textContent = '';
        if (!supportsMediaRecorder) {
            liveHelp.textContent = 'Live mode not supported in this browser.';
            return;
        }
        try {
            liveStatus.textContent = 'Setting up audio...';

            // Step 1: Get microphone access
            liveStream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Step 2: Set up AudioContext and AudioWorklet FIRST
            audioCtx = new AudioContext({ sampleRate: 16000 });
            const source = audioCtx.createMediaStreamSource(liveStream);

            await audioCtx.audioWorklet.addModule('data:text/javascript,' + encodeURIComponent(`
                class PCMProcessor extends AudioWorkletProcessor {
                    process(inputs, outputs, parameters) {
                        const input = inputs[0];
                        if (input && input[0]) {
                            const samples = input[0];
                            const pcm16 = new Int16Array(samples.length);
                            for (let i = 0; i < samples.length; i++) {
                                const s = Math.max(-1, Math.min(1, samples[i]));
                                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
                        }
                        return true;
                    }
                }
                registerProcessor('pcm-processor', PCMProcessor);
            `));

            pcmNode = new AudioWorkletNode(audioCtx, 'pcm-processor');

            console.log('[AudioWorklet] Ready, sample rate:', audioCtx.sampleRate);
            liveStatus.textContent = 'Connecting...';

            // Step 3: NOW create WebSocket (after audio is ready)
            const liveModel = getModelSize('live');
            ws = new WebSocket(withModelSize(WS_URL, liveModel));
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                console.log('[WS] Connected');
                liveStatus.textContent = 'Connected';
                // Send required start handshake
                ws.send(JSON.stringify({
                    type: 'start',
                    format: 's16le',
                    rate: 16000,
                    model_size: liveModel,
                }));
                console.log('[WS] Handshake sent');
                // Now enable the stop button
                setLiveEnabled(true);
            };

            ws.onclose = (e) => {
                console.log('[WS] Closed', e.code, e.reason);
                liveStatus.textContent = 'Disconnected';
                // Only update buttons if we were actually active
                if (isLiveActive) {
                    setLiveEnabled(false);
                }
            };

            ws.onerror = (e) => {
                console.error('[WS] Error', e);
                liveStatus.textContent = 'WS error';
            };

            ws.onmessage = (ev) => {
                try {
                    const msg = JSON.parse(ev.data);
                    console.log('[WS] Received:', msg.type);
                    if (msg.type === 'delta') {
                        if (msg.append && msg.append.length > 0) {
                            transcript += (transcript ? " " : "") + msg.append;
                            outLive.textContent = transcript;
                        }
                    } else if (msg.type === 'final') {
                        outLive.textContent = transcript + "\n[finalized]";
                    }
                } catch (e) {
                    console.error('[WS parse error]', e);
                }
            };

            // Step 4: Connect audio pipeline to send data via WebSocket
            pcmNode.port.onmessage = (e) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(e.data);
                }
            };

            source.connect(pcmNode);
            pcmNode.connect(audioCtx.destination);

            // Button state will be set in ws.onopen when connection succeeds
        } catch (err) {
            liveHelp.textContent = 'Mic access or WS failed: ' + err;
            liveStatus.textContent = 'Failed';
            setLiveEnabled(false);
            // Cleanup on error
            if (liveStream) liveStream.getTracks().forEach(t => t.stop());
            if (audioCtx) {
                try { audioCtx.close(); } catch { }
                audioCtx = null;
            }
            if (ws) {
                try { ws.close(); } catch { }
            }
        }
    };

    stopBtn.onclick = () => {
        try {
            if (pcmNode) {
                pcmNode.disconnect();
                pcmNode = null;
            }
        } catch {
        }
        try {
            if (audioCtx) {
                audioCtx.close();
                audioCtx = null;
            }
        } catch {
        }
        try {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('stop');
                // Give server time to process and close gracefully
                setTimeout(() => {
                    try {
                        ws?.close();
                    } catch { }
                }, 500);
            }
        } catch {
        }
        try {
            liveStream?.getTracks().forEach(t => t.stop());
        } catch {
        }
        setLiveEnabled(false);
    };

    // Detect live capability early
    if (!supportsMediaRecorder) {
        const tabLive = document.getElementById('tab-live');
        tabLive.classList.add('hidden');
        liveHelp.textContent = 'Live mode is hidden: MediaRecorder not supported by this browser.';
    }
}
