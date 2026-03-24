from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import json

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.cleaning import CLASSIFIER_VERSION, apply_filters, clean_and_classify_data
from src.data_fetch import (
    DEFAULT_QUERY,
    fetch_trials_from_api,
    load_cached_csv,
    save_metadata_json,
    save_raw_csv,
)
from src.export import dataframe_to_csv_bytes, write_run_artifacts
from src.visuals import figure_to_png_bytes, generate_figure_1, generate_figure_2, prepare_publication_df


APP_VERSION = "1.0.0"
CACHE_DIR = Path("data/cache")
RAW_CACHE_CSV = CACHE_DIR / "raw_trials_with_reason.csv"
RAW_CACHE_META = CACHE_DIR / "fetch_metadata.json"
ARTIFACTS_DIR = Path("data/artifacts")
LOCAL_RAW_CSV = Path("raw_trials_with_reason.csv")
MAX_HISTORY = 5


st.set_page_config(page_title="Clinical Trial Termination Dashboard", layout="wide")
st.title("Clinical Trial Termination Dashboard")
st.caption("Fetch, clean, and visualize terminated Phase II/III trials from ClinicalTrials.gov.")
if "run_history" not in st.session_state:
    st.session_state["run_history"] = []


def _status(msg: str) -> None:
    st.session_state["last_status"] = msg
    st.info(msg)


@st.cache_data(show_spinner=False)
def _cached_clean(df: pd.DataFrame) -> pd.DataFrame:
    return clean_and_classify_data(df)


def _load_or_fetch_data(use_cache: bool, query: str) -> tuple[pd.DataFrame, dict]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if use_cache:
        if not RAW_CACHE_CSV.exists():
            raise FileNotFoundError("No cached raw CSV exists yet. Fetch from API first.")
        raw_df = load_cached_csv(RAW_CACHE_CSV)
        metadata = {
            "source": "cache",
            "query": query,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "row_count": len(raw_df),
            "app_version": APP_VERSION,
            "classifier_version": CLASSIFIER_VERSION,
        }
        return raw_df, metadata

    try:
        raw_df, api_meta = fetch_trials_from_api(query=query, max_retries=3, retry_sleep_sec=1.5)
        save_raw_csv(raw_df, RAW_CACHE_CSV)
        save_metadata_json(api_meta, RAW_CACHE_META)
        return raw_df, api_meta.__dict__
    except Exception as exc:  # noqa: BLE001
        if RAW_CACHE_CSV.exists():
            raw_df = load_cached_csv(RAW_CACHE_CSV)
            metadata = {
                "source": "cache_fallback_after_api_error",
                "api_error": str(exc),
                "query": query,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "row_count": len(raw_df),
                "app_version": APP_VERSION,
                "classifier_version": CLASSIFIER_VERSION,
            }
            st.warning("API request failed; using cached data instead.")
            return raw_df, metadata
        if LOCAL_RAW_CSV.exists():
            raw_df = load_cached_csv(LOCAL_RAW_CSV)
            metadata = {
                "source": "local_csv_fallback_after_api_error",
                "api_error": str(exc),
                "query": query,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "row_count": len(raw_df),
                "app_version": APP_VERSION,
                "classifier_version": CLASSIFIER_VERSION,
            }
            st.warning("API request failed; using local raw_trials_with_reason.csv fallback.")
            return raw_df, metadata
        raise


with st.sidebar:
    st.header("Parameters")
    start_year, end_year = st.slider("Year range", 2015, 2025, (2015, 2024))
    phase_option = st.selectbox("Phase filter", ["Both", "Phase II", "Phase III"], index=0)
    sponsor_class = st.selectbox("Sponsor class", ["INDUSTRY", "NIH", "OTHER", "ALL"], index=0)
    use_cache = st.toggle("Use cached data", value=False)
    save_server_artifacts = st.toggle("Save server-side artifacts", value=False)
    query = st.text_area("API query", value=DEFAULT_QUERY, height=120)
    run = st.button("Run Analysis", type="primary", use_container_width=True)

if run:
    if start_year > end_year:
        st.error("Start year must be <= end year.")
    else:
        try:
            _status("Loading data...")
            raw_df, run_meta = _load_or_fetch_data(use_cache=use_cache, query=query)

            _status("Cleaning and classifying data...")
            tidy_df = _cached_clean(raw_df)
            filtered_df = apply_filters(
                tidy_df,
                start_year=start_year,
                end_year=end_year,
                phase_option=phase_option,
                sponsor_class="" if sponsor_class == "ALL" else sponsor_class,
            )
            if filtered_df.empty:
                st.warning("No rows match the selected parameters.")
            else:
                run_meta.update(
                    {
                        "run_at_utc": datetime.now(timezone.utc).isoformat(),
                        "parameter_start_year": start_year,
                        "parameter_end_year": end_year,
                        "parameter_phase": phase_option,
                        "parameter_sponsor_class": sponsor_class,
                    }
                )

                total_trials = len(filtered_df)
                avg_per_year = (
                    filtered_df.groupby("year_int").size().mean() if "year_int" in filtered_df.columns else 0
                )
                unknown_share = (
                    (filtered_df["termination_category"] == "Unknown").mean() * 100
                    if "termination_category" in filtered_df.columns
                    else 0
                )

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Terminated Trials", f"{total_trials:,}")
                col2.metric("Average per Year", f"{avg_per_year:.1f}")
                col3.metric("Unknown Category Share", f"{unknown_share:.1f}%")

                st.subheader("Visualizations")
                selected_years = list(range(start_year, end_year + 1))
                pub_df = prepare_publication_df(filtered_df, start_year=start_year, end_year=end_year)
                fig1 = generate_figure_1(pub_df, years=selected_years)
                fig2 = generate_figure_2(pub_df, years=selected_years)
                fig1_png = figure_to_png_bytes(fig1)
                fig2_png = figure_to_png_bytes(fig2)
                plt.close(fig1)
                plt.close(fig2)
                st.image(fig1_png, caption="Figure 1 (Bowling-style publication format)", use_container_width=True)
                st.image(fig2_png, caption="Figure 2 (Bowling-style publication format)", use_container_width=True)

                st.subheader("Exports")
                run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    "Download cleaned CSV",
                    data=dataframe_to_csv_bytes(filtered_df),
                    file_name=f"cleaned_trials_{run_id}.csv",
                    mime="text/csv",
                )
                st.download_button(
                    "Download Figure 1 (PNG)",
                    data=fig1_png,
                    file_name=f"figure1_termination_reasons_{run_id}.png",
                    mime="image/png",
                )
                st.download_button(
                    "Download Figure 2 (PNG)",
                    data=fig2_png,
                    file_name=f"figure2_termination_trends_{run_id}.png",
                    mime="image/png",
                )
                st.caption("Downloads save to your local Downloads folder in the browser.")

                st.session_state["run_history"] = (
                    [
                        {
                            "run_id": run_id,
                            "rows": len(filtered_df),
                            "csv": dataframe_to_csv_bytes(filtered_df),
                            "fig1": fig1_png,
                            "fig2": fig2_png,
                            "meta": json.dumps(run_meta, indent=2).encode("utf-8"),
                        }
                    ]
                    + st.session_state["run_history"]
                )[:MAX_HISTORY]

                with st.expander("Recent runs (this session)"):
                    if st.session_state["run_history"]:
                        options = [f"{item['run_id']} | rows={item['rows']}" for item in st.session_state["run_history"]]
                        selected = st.selectbox("Select a previous run", options=options)
                        selected_idx = options.index(selected)
                        selected_run = st.session_state["run_history"][selected_idx]
                        st.download_button(
                            "Download selected run CSV",
                            data=selected_run["csv"],
                            file_name=f"cleaned_trials_{selected_run['run_id']}.csv",
                            mime="text/csv",
                            key=f"hist_csv_{selected_run['run_id']}",
                        )
                        st.download_button(
                            "Download selected run Figure 1",
                            data=selected_run["fig1"],
                            file_name=f"figure1_termination_reasons_{selected_run['run_id']}.png",
                            mime="image/png",
                            key=f"hist_fig1_{selected_run['run_id']}",
                        )
                        st.download_button(
                            "Download selected run Figure 2",
                            data=selected_run["fig2"],
                            file_name=f"figure2_termination_trends_{selected_run['run_id']}.png",
                            mime="image/png",
                            key=f"hist_fig2_{selected_run['run_id']}",
                        )

                if save_server_artifacts:
                    artifacts = write_run_artifacts(
                        ARTIFACTS_DIR,
                        cleaned_df=filtered_df,
                        metadata=run_meta,
                        chart_png_bytes={"figure1_termination_reasons": fig1_png, "figure2_termination_trends": fig2_png},
                    )
                    st.success("Run artifacts saved on server filesystem.")
                    st.code("\n".join([str(path) for path in artifacts.values()]), language="text")
                    if os.getenv("STREAMLIT_SHARING_MODE"):
                        st.info("Cloud hosts may clear server files after restarts. Use download buttons for permanent copies.")

                with st.expander("Run metadata"):
                    st.json(run_meta)
                    st.download_button(
                        "Download metadata JSON",
                        data=json.dumps(run_meta, indent=2).encode("utf-8"),
                        file_name="run_metadata.json",
                        mime="application/json",
                    )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Run failed: {exc}")
else:
    st.info("Set parameters in the sidebar and click Run Analysis.")
