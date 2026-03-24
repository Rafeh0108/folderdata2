from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


CLASSIFIER_VERSION = "1.0.0"


@dataclass(frozen=True)
class Rule:
    category: str
    keywords: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule("Safety", ("safety", "adverse", "toxicity", "harm", "sae", "death", "mortality", "tolerability")),
    Rule(
        "Efficacy",
        ("efficacy", "effectiveness", "lack of effect", "lack of benefit", "futility", "endpoint"),
    ),
    Rule("Enrolment", ("enrollment", "enrolment", "recruit", "accru", "screen failure", "eligib")),
    Rule(
        "Strategy/Business",
        ("business", "strateg", "commercial", "portfolio", "sponsor decision", "merger", "funding withdrawn"),
    ),
    Rule("Operational", ("operational", "logistic", "protocol issue", "manufactur", "covid", "budget", "site issue")),
)


def extract_year(date_str: str | float | int | None) -> float | int:
    if pd.isna(date_str):
        return np.nan
    match = re.search(r"\b(201[5-9]|202[0-5])\b", str(date_str))
    return int(match.group(1)) if match else np.nan


def classify_reason(reason: str | float | int | None, rules: Iterable[Rule] = RULES) -> str:
    if pd.isna(reason):
        return "Unknown"

    normalized_reason = str(reason).lower()
    for rule in rules:
        if any(keyword in normalized_reason for keyword in rule.keywords):
            return rule.category
    return "Unknown"


def clean_and_classify_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned = cleaned.replace(["", "nan", "None", "N/A", "n/a", "NaN"], np.nan)
    cleaned["year"] = cleaned["primary_completion_date"].apply(extract_year)
    cleaned["termination_category"] = cleaned["why_stopped"].apply(classify_reason)
    return cleaned


def apply_filters(
    df: pd.DataFrame,
    start_year: int,
    end_year: int,
    phase_option: str = "Both",
    sponsor_class: str = "INDUSTRY",
) -> pd.DataFrame:
    if start_year > end_year:
        raise ValueError("Start year cannot be greater than end year.")

    working = df.copy()
    working["year_int"] = pd.to_numeric(working["year"], errors="coerce").astype("Int64")
    working = working[working["year_int"].between(start_year, end_year)]

    if sponsor_class and "funder_type" in working.columns:
        working = working[working["funder_type"].fillna("").str.upper() == sponsor_class.upper()]

    phase_text = working["phase"].fillna("").astype(str)
    if phase_option == "Phase II":
        working = working[phase_text.str.contains("2", na=False)]
    elif phase_option == "Phase III":
        working = working[phase_text.str.contains("3", na=False)]

    return working
