// API Configuration
export const API_BASE = ''; // same origin
export const POST_URL = `${API_BASE}/transcribe`;
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss' : 'ws';
export const WS_URL = `${WS_PROTOCOL}://${window.location.host}/ws/transcribe`;

export function withModelSize(url, modelSize) {
    const resolved = new URL(url, window.location.origin);
    if (modelSize) {
        resolved.searchParams.set('model_size', modelSize);
    }
    return resolved.toString();
}
