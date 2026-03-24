# Clinical Trial Termination App

A professor-friendly web app that fetches terminated clinical trial records from ClinicalTrials.gov, cleans and classifies termination reasons, and produces Bowling-style publication figures with downloadable outputs.

## Features

- Parameterized analysis (`year range`, `phase`, `sponsor class`, custom query)
- API fetch with retries and local cache fallback
- Deterministic rule-based reason classification
- Publication-style Figure 1/2 rendering (Bowling format)
- Per-run downloads (CSV + figure PNGs + metadata JSON)
- In-session recent run history (up to 5 runs) for easy compare/download
- Optional server-side run artifacts for reproducibility

## Project Structure

- `app.py` - Streamlit app entrypoint
- `src/data_fetch.py` - API fetch, retries, caching helpers
- `src/cleaning.py` - cleaning, year extraction, classification, filtering
- `src/visuals.py` - KPI support and chart construction
- `src/export.py` - download and artifact generation
- `data/cache/` - cached raw data + fetch metadata
- `data/artifacts/` - timestamped run exports

## Local Run

1. Create/activate virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start app:
   - `streamlit run app.py`
4. Open the local URL shown in terminal.

## Professor Demo Flow

1. Open app URL.
2. Keep defaults (`2015-2024`, `Both`, `INDUSTRY`) and click **Run Analysis**.
3. Review KPI cards and publication figures.
4. Download CSV/figures directly to local machine.
5. Optionally compare and download from **Recent runs (this session)**.

## Deployment (Streamlit Community Cloud)

1. Push this folder to a GitHub repository.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Create a new app, choose your repo and branch, set entrypoint to `app.py`.
4. Deploy and copy public URL for your professor.
5. In app usage, keep **Save server-side artifacts** off for professor sessions; use download buttons for permanent local copies.

## Deployment (Render Alternative)

1. Create a new **Web Service** from your GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. Deploy and share URL.

## Reliability Notes

- If API is unavailable, toggle **Use cached data** (after at least one successful fetch).
- Every run stores metadata including query, timestamp, app version, and classifier version.
- Server-side files on cloud hosts can be temporary; downloaded files are the reliable final output.

## Optional Desktop Packaging

See `DESKTOP_WRAPPER_PLAN.md` for a follow-up Windows/macOS packaging path.
