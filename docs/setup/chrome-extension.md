# Chrome Extension Setup Guide

## Prerequisites
- Google Chrome or Chromium-based browser (v110+)
- Node.js 18+ and npm installed
- FastAPI Backend running on `http://localhost:8000`

## Build Steps
From the repository root:
```bash
cd apps/browser-extension
npm install
npm run build
```
This produces bundled files in `apps/browser-extension/dist/`.

## Loading into Chrome
1. Open Google Chrome.
2. Navigate to `chrome://extensions/`.
3. Toggle on **Developer mode** in the top right corner.
4. Click **Load unpacked**.
5. Select the directory:
   ```text
   <repo-root>/apps/browser-extension/dist
   ```
6. The extension **TechVerse AI Browser Agent** will appear with its icon in the Chrome toolbar.

## Pairing with Local Backend
1. Start your local FastAPI backend:
   ```bash
   uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Open the TechVerse dashboard or request a pairing code via API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/agent/browser/challenge -H "X-Organization-ID: <your-org-uuid>"
   ```
   Output:
   ```json
   { "pairing_code": "TV-ABCD-1234", "expires_in_seconds": 300 }
   ```
3. Click the **TechVerse AI** extension icon in Chrome toolbar.
4. Enter `TV-ABCD-1234` into the Pairing Code field and click **Connect**.
5. The extension status updates to `Connected` (Green indicator).
