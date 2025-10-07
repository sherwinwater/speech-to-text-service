/**
 * Initialize tab switching functionality
 */
export function initTabs() {
    const tabUpload = document.getElementById('tab-upload');
    const tabRecord = document.getElementById('tab-record');
    const tabLive = document.getElementById('tab-live');
    const panelUpload = document.getElementById('panel-upload');
    const panelRecord = document.getElementById('panel-record');
    const panelLive = document.getElementById('panel-live');

    function setTab(which) {
        tabUpload.classList.toggle('active', which === 'upload');
        tabRecord.classList.toggle('active', which === 'record');
        tabLive.classList.toggle('active', which === 'live');
        panelUpload.classList.toggle('hidden', which !== 'upload');
        panelRecord.classList.toggle('hidden', which !== 'record');
        panelLive.classList.toggle('hidden', which !== 'live');
    }

    tabUpload.onclick = () => setTab('upload');
    tabRecord.onclick = () => setTab('record');
    tabLive.onclick = () => setTab('live');
}
