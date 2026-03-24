# Optional Desktop Wrapper Plan

After the web app is stable, package it as a downloadable app for macOS and Windows.

## Option A: PyInstaller (Fastest)

- Bundle Python + Streamlit app into executable
- Start local server on launch and auto-open browser window
- Produce:
  - macOS `.app`/`.dmg`
  - Windows `.exe` installer

## Option B: Tauri Wrapper (Most polished UX)

- Keep Python backend for analytics
- Build native shell UI for app launch/config
- Better native integration, smaller polished app shell

## Suggested Steps

1. Freeze dependencies and verify web app stability.
2. Add startup script:
   - launch Streamlit on free local port
   - open browser to local URL
3. Build per OS with CI workflows (GitHub Actions).
4. Sign binaries if required by your institution policy.
5. Publish installers and short install guide.
