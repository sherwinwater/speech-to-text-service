import { POST_URL } from '../config/config.js';

/**
 * Initialize upload mode functionality
 */
export function initUpload() {
    const fileInput = document.getElementById('file');
    const sendBtn = document.getElementById('send');
    const outUpload = document.getElementById('out-upload');

    sendBtn.onclick = async () => {
        const f = fileInput.files?.[0];
        if (!f) {
            outUpload.textContent = 'Please choose a file.';
            return;
        }
        const form = new FormData();
        form.append('file', f, f.name);
        outUpload.textContent = 'Uploading…';
        try {
            const res = await fetch(POST_URL, { method: 'POST', body: form });
            const js = await res.json();
            outUpload.textContent = js.text ? js.text : JSON.stringify(js, null, 2);
        } catch (err) {
            outUpload.textContent = 'Error: ' + err;
        }
    };
}
