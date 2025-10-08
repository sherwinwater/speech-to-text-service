import { POST_URL, withModelSize } from '../config/config.js';
import { getModelSize } from '../components/modelSelector.js';

/**
 * Initialize upload mode functionality
 */
export function initUpload() {
    const fileInput = document.getElementById('file');
    const sendBtn = document.getElementById('send');
    const outUpload = document.getElementById('out-upload');
    const SUPPORTED = ['wav', 'mp3', 'm4a', 'ogg', 'webm', 'flac'];
    const MAX_FILE_MB = 100; // keep in sync with server default

    sendBtn.onclick = async () => {
        const f = fileInput.files?.[0];
        if (!f) {
            outUpload.textContent = 'Please choose a file.';
            return;
        }
        const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
        if (!SUPPORTED.includes(ext)) {
            outUpload.textContent = `Unsupported file type. Supported: ${SUPPORTED.join(', ')}`;
            return;
        }
        const maxBytes = MAX_FILE_MB * 1024 * 1024;
        if (f.size > maxBytes) {
            outUpload.textContent = `File is too large (>${MAX_FILE_MB}MB). Please choose a smaller file.`;
            return;
        }
        const form = new FormData();
        form.append('file', f, f.name);
        outUpload.textContent = 'Uploading…';
        try {
            const modelSize = getModelSize('upload');
            const url = withModelSize(POST_URL, modelSize);
            const res = await fetch(url, { method: 'POST', body: form });
            let js = null;
            try {
                js = await res.json();
            } catch (parseErr) {
                // ignore – non-JSON response
            }
            if (!res.ok) {
                const detail = js?.detail ?? js?.error ?? res.statusText;
                outUpload.textContent = `Error (${res.status}): ${detail}`;
                return;
            }
            outUpload.textContent = js?.text ? js.text : JSON.stringify(js, null, 2);
        } catch (err) {
            outUpload.textContent = 'Error: ' + err;
        }
    };
}
