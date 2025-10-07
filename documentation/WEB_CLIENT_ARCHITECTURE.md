# Web Client Architecture

## Clean Architecture for Frontend

The web client has been refactored to follow clean architecture principles with proper separation of concerns.

## Directory Structure

```
client/web/
├── index.html                  # HTML entry point
├── index-old.html              # Backup
├── README.md                   # Documentation
│
├── css/                        # Presentation Layer
│   └── styles.css              # All styling
│
└── js/                         # JavaScript Layer
    ├── app.js                  # Application entry point
    │
    ├── config/                 # Configuration Layer
    │   └── config.js           # API endpoints, settings
    │
    ├── components/             # UI Components Layer
    │   └── tabs.js             # Tab switching component
    │
    └── services/               # Business Logic Layer
        ├── upload.js           # File upload service
        ├── record.js           # Microphone recording service
        └── live.js             # WebSocket streaming service
```

## Layer Responsibilities

### 1. Presentation Layer (`css/`)
**Purpose**: Visual styling

**Files**:
- `styles.css` - All CSS rules

**Responsibilities**:
- Layout (flexbox, grid)
- Colors and typography
- Responsive design
- Visual states

---

### 2. Configuration Layer (`js/config/`)
**Purpose**: Application configuration

**Files**:
- `config.js` - API URLs and constants

**Responsibilities**:
- API endpoint URLs
- Application constants
- Environment-specific settings

**Example**:
```javascript
export const API_BASE = '';
export const POST_URL = `${API_BASE}/transcribe`;
export const WS_URL = `ws://${location.host}/ws/transcribe`;
```

---

### 3. Components Layer (`js/components/`)
**Purpose**: Reusable UI components

**Files**:
- `tabs.js` - Tab switching logic

**Responsibilities**:
- DOM manipulation
- Event handling
- UI state management
- Component lifecycle

**Example**:
```javascript
export function initTabs() {
    // Handle tab switching
    // Manage active states
    // Show/hide panels
}
```

---

### 4. Services Layer (`js/services/`)
**Purpose**: Business logic and API communication

**Files**:
- `upload.js` - File upload functionality
- `record.js` - Microphone recording
- `live.js` - WebSocket streaming

**Responsibilities**:
- API calls
- Data processing
- State management
- Error handling
- WebSocket communication

**Example**:
```javascript
export function initUpload() {
    // Handle file selection
    // Upload to API
    // Display results
}
```

---

### 5. Entry Point (`js/app.js`)
**Purpose**: Application initialization

**Responsibilities**:
- Import all modules
- Initialize components
- Bootstrap application

**Example**:
```javascript
import { initTabs } from './components/tabs.js';
import { initUpload } from './services/upload.js';
import { initRecord } from './services/record.js';
import { initLive } from './services/live.js';

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initUpload();
    initRecord();
    initLive();
});
```

## Import Graph

```
index.html
    ↓
js/app.js
    ↓
├── components/tabs.js
├── services/upload.js
├── services/record.js
└── services/live.js
    ↓
config/config.js
```

## Benefits

### ✅ Clear Separation of Concerns
- **CSS**: Styling only
- **Config**: Configuration only
- **Components**: UI logic only
- **Services**: Business logic only

### ✅ Easy to Navigate
Looking for:
- Styles? → `css/`
- API URLs? → `js/config/`
- UI components? → `js/components/`
- Business logic? → `js/services/`

### ✅ Modular & Reusable
Each service can be:
- Tested independently
- Reused in other projects
- Modified without affecting others

### ✅ Scalable
Easy to add:
- New styles → Add to `css/`
- New config → Add to `config/`
- New component → Add to `components/`
- New feature → Add to `services/`

### ✅ Maintainable
Changes are isolated:
- Style change? → Edit `css/`
- API change? → Edit `config/`
- UI change? → Edit `components/`
- Logic change? → Edit `services/`

## Comparison: Before vs After

### Before (Flat Structure)
```
web/
├── index.html
├── app.js
├── config.js
├── tabs.js
├── upload.js
├── record.js
├── live.js
└── styles.css

All files in root - hard to organize
```

### After (Organized Structure)
```
web/
├── index.html
├── css/
│   └── styles.css
└── js/
    ├── app.js
    ├── config/
    │   └── config.js
    ├── components/
    │   └── tabs.js
    └── services/
        ├── upload.js
        ├── record.js
        └── live.js

Clear organization - easy to navigate
```

## Module Descriptions

### `config/config.js`
```javascript
// API endpoint configuration
export const API_BASE = '';
export const POST_URL = `${API_BASE}/transcribe`;
export const WS_URL = `ws://${location.host}/ws/transcribe`;
```

**Purpose**: Centralize all configuration
**Dependencies**: None

---

### `components/tabs.js`
```javascript
// Tab switching component
export function initTabs() {
    // Get tab elements
    // Add click handlers
    // Toggle active states
    // Show/hide panels
}
```

**Purpose**: Manage tab navigation
**Dependencies**: None (pure DOM)

---

### `services/upload.js`
```javascript
// File upload service
export function initUpload() {
    // Handle file selection
    // Validate file
    // Upload via FormData
    // Display transcript
}
```

**Purpose**: File upload functionality
**Dependencies**: `config/config.js`

---

### `services/record.js`
```javascript
// Microphone recording service
export function initRecord() {
    // Request mic access
    // Use MediaRecorder API
    // Record audio
    // Upload and transcribe
}
```

**Purpose**: Microphone recording
**Dependencies**: `config/config.js`

---

### `services/live.js`
```javascript
// WebSocket streaming service
export function initLive() {
    // Setup AudioWorklet
    // Connect WebSocket
    // Stream PCM audio
    // Display real-time transcripts
}
```

**Purpose**: Real-time streaming
**Dependencies**: `config/config.js`

## Design Patterns

### 1. Module Pattern
Each file exports specific functions:
```javascript
export function initUpload() { ... }
export function initRecord() { ... }
```

### 2. Dependency Injection
Services import only what they need:
```javascript
import { POST_URL } from '../config/config.js';
```

### 3. Single Responsibility
Each module has one clear purpose:
- `tabs.js` - Tab switching only
- `upload.js` - File upload only
- `record.js` - Recording only
- `live.js` - Streaming only

### 4. Separation of Concerns
- HTML - Structure
- CSS - Presentation
- JS - Behavior

## File Naming Conventions

### Directories
- `css/` - Stylesheets
- `js/` - JavaScript
- `js/config/` - Configuration
- `js/components/` - UI components
- `js/services/` - Business logic

### Files
- `config.js` - Configuration
- `tabs.js` - Component name
- `upload.js` - Service name
- `styles.css` - Stylesheet

## Import Paths

### From `app.js`
```javascript
import { initTabs } from './components/tabs.js';
import { initUpload } from './services/upload.js';
```

### From Services
```javascript
import { POST_URL } from '../config/config.js';
```

### In HTML
```html
<link rel="stylesheet" href="css/styles.css">
<script type="module" src="js/app.js"></script>
```

## Testing Strategy

### Unit Tests
```javascript
// Test individual services
test('upload service handles file', () => {
    const service = initUpload();
    // Test file upload logic
});

test('record service handles recording', () => {
    const service = initRecord();
    // Test recording logic
});
```

### Integration Tests
```javascript
// Test component integration
test('tabs switch correctly', () => {
    initTabs();
    // Click tab
    // Verify panel visibility
});
```

### End-to-End Tests
```javascript
// Test full user flows
test('upload flow works', () => {
    // Select file
    // Click upload
    // Verify transcript
});
```

## Future Enhancements

### Potential Additions
- `js/utils/` - Utility functions
- `js/models/` - Data models
- `js/api/` - API client layer
- `js/state/` - State management
- `css/components/` - Component-specific styles
- `css/base/` - Base styles
- `css/themes/` - Theme files

### Advanced Patterns
- State management (Redux, MobX)
- Component framework (React, Vue)
- Build tools (Webpack, Vite)
- TypeScript for type safety
- CSS preprocessor (SASS, LESS)

## Summary

### What We Achieved
1. ✅ Organized files into logical directories
2. ✅ Separated concerns (CSS, config, components, services)
3. ✅ Updated all imports to new paths
4. ✅ Maintained functionality (no breaking changes)
5. ✅ Improved maintainability and scalability

### Result
**Clean, organized frontend architecture** with:
- Clear directory structure
- Logical file organization
- Easy to navigate
- Easy to maintain
- Easy to extend
- Professional structure

---

**Status**: 🟢 **WEB CLIENT REFACTORED**  
**Pattern**: Layered Frontend Architecture  
**Quality**: 🌟 **PRODUCTION-READY**
