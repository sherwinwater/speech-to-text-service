# Web Client Structure

This directory contains the refactored web client for the Speech-to-Text service, organized with clean architecture principles.

## File Structure

```
web/
├── index.html              # Main HTML entry point
├── index-old.html          # Backup of original monolithic file
├── README.md               # This file
│
├── css/                    # Stylesheets
│   └── styles.css          # All CSS styles
│
└── js/                     # JavaScript modules
    ├── app.js              # Main entry point
    │
    ├── config/             # Configuration
    │   └── config.js       # API URLs and settings
    │
    ├── components/         # UI Components
    │   └── tabs.js         # Tab switching logic
    │
    └── services/           # Business Logic
        ├── upload.js       # Upload mode functionality
        ├── record.js       # Record mode functionality
        └── live.js         # Live streaming mode functionality
```

## Architecture

### Modular Design
Each feature is isolated in its own JavaScript module:

- **config.js**: Centralized API endpoints configuration
- **tabs.js**: Handles tab switching between Upload/Record/Live modes
- **upload.js**: File upload and transcription
- **record.js**: Microphone recording → upload → transcribe
- **live.js**: Real-time WebSocket streaming with AudioWorklet

### Benefits
1. **Separation of Concerns**: Each module has a single responsibility
2. **Maintainability**: Easy to update individual features
3. **Testability**: Modules can be tested independently
4. **Readability**: Clean HTML, organized CSS, modular JS
5. **Reusability**: Modules can be imported elsewhere if needed

## Usage

The application uses ES6 modules. Make sure your server serves the files with correct MIME types:
- `.js` files as `application/javascript` or `text/javascript`
- `.css` files as `text/css`

Modern browsers support ES6 modules natively via `<script type="module">`.

## Development

To modify a specific feature:
1. Edit the corresponding `.js` file
2. Reload the page (modules are loaded fresh each time)
3. Check browser console for any errors

## Rollback

If you need to revert to the original monolithic version:
```bash
mv index.html index-refactored.html
mv index-old.html index.html
```
