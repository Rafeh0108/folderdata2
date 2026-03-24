from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
import requests


DEFAULT_QUERY = (
    "AREA[OverallStatus]TERMINATED AND AREA[Phase](PHASE2 OR PHASE3) "
    "AND AREA[LeadSponsorClass]INDUSTRY "
    "AND AREA[PrimaryCompletionDate]RANGE[2015-01-01,2025-01-01]"
)
API_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


@dataclass
class FetchMetadata:
    query: str
    fetched_at_utc: str
    row_count: int
    api_base_url: str = API_BASE_URL
    source: str = "api"
    app_version: str = "1.0.0"
    classifier_version: str = "1.0.0"


def _normalize_study(study: dict[str, Any]) -> dict[str, Any]:
    protocol = study.get("protocolSection", {})
    id_mod = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})

    phases = design_mod.get("phases", [])
    phase_str = "|".join(phases) if phases else ""

    return {
        "nct_id": id_mod.get("nctId", ""),
        "study_title": id_mod.get("briefTitle", ""),
        "study_status": status_mod.get("overallStatus", ""),
        "phase": phase_str,
        "sponsor": sponsor_mod.get("leadSponsor", {}).get("name", ""),
        "funder_type": sponsor_mod.get("leadSponsor", {}).get("class", ""),
        "conditions": "",
        "interventions": "",
        "enrollment": design_mod.get("enrollmentInfo", {}).get("count", ""),
        "start_date": "",
        "primary_completion_date": status_mod.get("primaryCompletionDateStruct", {}).get("date", ""),
        "completion_date": "",
        "first_posted": "",
        "why_stopped": status_mod.get("whyStopped", ""),
        "study_type": "",
        "study_design": "",
    }


def fetch_trials_from_api(
    query: str = DEFAULT_QUERY,
    page_size: int = 1000,
    timeout: int = 30,
    max_retries: int = 3,
    retry_sleep_sec: float = 1.0,
    allow_insecure_ssl_fallback: bool = True,
) -> tuple[pd.DataFrame, FetchMetadata]:
    encoded_query = urllib.parse.quote(query)
    base_url = f"{API_BASE_URL}?query.term={encoded_query}&pageSize={page_size}"

    all_studies: list[dict[str, Any]] = []
    next_page_token = None

    while True:
        url = base_url if not next_page_token else f"{base_url}&pageToken={next_page_token}"

        data = None
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                # First path: requests session with browser-like headers.
                response = requests.get(
                    url,
                    headers=DEFAULT_HEADERS,
                    timeout=timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                # Second path: urllib in case requests path is blocked.
                try:
                    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    break
                except Exception as urllib_exc:  # noqa: BLE001
                    last_error = urllib_exc
                # Match notebook behavior on macOS networks with self-signed SSL chains.
                if allow_insecure_ssl_fallback and "CERTIFICATE_VERIFY_FAILED" in str(last_error):
                    unverified_ctx = ssl._create_unverified_context()
                    try:
                        with urllib.request.urlopen(req, timeout=timeout, context=unverified_ctx) as response:
                            data = json.loads(response.read().decode("utf-8"))
                        break
                    except Exception as insecure_exc:  # noqa: BLE001
                        last_error = insecure_exc
                if attempt < max_retries:
                    time.sleep(retry_sleep_sec * attempt)
        if data is None:
            raise RuntimeError(f"API request failed after {max_retries} retries: {last_error}")

        studies = data.get("studies", [])
        all_studies.extend(studies)

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        time.sleep(0.3)

    if not all_studies:
        raise RuntimeError("API returned zero studies.")

    rows = [_normalize_study(study) for study in all_studies]
    df = pd.DataFrame(rows)
    metadata = FetchMetadata(
        query=query,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        row_count=len(df),
    )
    return df, metadata


def save_raw_csv(df: pd.DataFrame, output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    csv.field_size_limit(10_000_000)
    df.to_csv(out, index=False, encoding="utf-8")
    return out


def save_metadata_json(metadata: FetchMetadata, output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metadata.__dict__, indent=2), encoding="utf-8")
    return out


def load_cached_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Cached file not found: {csv_path}")
    return pd.read_csv(csv_path)
