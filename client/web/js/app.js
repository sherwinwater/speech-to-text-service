import { initTabs } from './components/tabs.js';
import { initModelSelectors } from './components/modelSelector.js';
import { initUpload } from './services/upload.js';
import { initRecord } from './services/record.js';
import { initLive } from './services/live.js';

/**
 * Main application entry point
 */
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initModelSelectors();
    initUpload();
    initRecord();
    initLive();
});
