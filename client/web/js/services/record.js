import { POST_URL } from '../config/config.js';

/**
 * Initialize record mode functionality
 */
export function initRecord() {
    const recBtn = document.getElementById('rec');
    const stopRecBtn = document.getElementById('stopRec');
    const outRecord = document.getElementById('out-record');
    const recStatus = document.getElementById('recStatus');

    let mediaRecorder, chunks = [];

    recBtn.onclick = async () => {
        chunks = [];
        outRecord.textContent = '';
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

            mediaRecorder.ondataavailable = e => {
                if (e.data && e.data.size > 0) {
                    chunks.push(e.data);
                }
            };

            mediaRecorder.onstop = async () => {
                recStatus.textContent = 'Processing...';
                const blob = new Blob(chunks, { type: 'audio/webm' });
                const form = new FormData();
                form.append('file', blob, 'recording.webm');

                try {
                    const res = await fetch(POST_URL, { method: 'POST', body: form });
                    const js = await res.json();
                    outRecord.textContent = js.text ? js.text : JSON.stringify(js, null, 2);
                    recStatus.textContent = '';
                } catch (err) {
                    outRecord.textContent = 'Error: ' + err;
                    recStatus.textContent = '';
                }

                // Stop all tracks
                stream.getTracks().forEach(t => t.stop());
            };

            mediaRecorder.start();
            recBtn.disabled = true;
            stopRecBtn.disabled = false;
            recStatus.textContent = 'Recording...';
        } catch (err) {
            outRecord.textContent = 'Microphone access failed: ' + err;
        }
    };

    stopRecBtn.onclick = () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            recBtn.disabled = false;
            stopRecBtn.disabled = true;
        }
    };
}
