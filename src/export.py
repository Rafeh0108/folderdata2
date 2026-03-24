from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

import pandas as pd


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def write_run_artifacts(
    output_dir: str | Path,
    cleaned_df: pd.DataFrame,
    metadata: dict[str, Any],
    chart_png_bytes: dict[str, bytes],
) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    run_stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = output_path / f"run_{run_stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cleaned_csv = run_dir / "cleaned_trials.csv"
    cleaned_df.to_csv(cleaned_csv, index=False)

    metadata_json = run_dir / "metadata.json"
    metadata_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    saved = {"cleaned_csv": cleaned_csv, "metadata_json": metadata_json}
    for chart_name, png_bytes in chart_png_bytes.items():
        chart_file = run_dir / f"{chart_name}.png"
        chart_file.write_bytes(png_bytes)
        saved[f"{chart_name}_png"] = chart_file

    return saved
