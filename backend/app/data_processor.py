"""
WindWise Backend — Data processing and analytics engine.

Terminology
-----------
delivery interval : a 30-minute settlement period on a given settlement date
                    identified by (settlementDate, settlementPeriod).
publishTime       : the UTC timestamp when National Grid ESO released a forecast.
cutoff            : the purchasing-decision deadline for delivery date D is
                    D-1 at 09:20 UTC (EPEX SPOT GB day-ahead gate closure).
eligible forecast : a WINDFOR record whose publishTime ≤ cutoff for its delivery date.
selected forecast : the latest eligible forecast for each delivery interval.

Data notes
----------
- This module processes WIND generation only (MW).
- Positive signed error = overforecast (forecast > actual).
- RMSE and MAE are in MW.
- Percentage errors are NOT calculated because actual generation can be zero.
- This dataset does NOT contain consumer demand, prices, thermal availability
  or total system generation. Procurement requirements cannot be derived here.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
from dateutil import parser as dateparser

from app.config import settings

logger = logging.getLogger(__name__)

# ── Cutoff definition ────────────────────────────────────────────────────────
CUTOFF_HOUR = settings.forecast_cutoff_hour    # default 9 (UTC)
CUTOFF_MINUTE = settings.forecast_cutoff_minute  # default 20 (UTC)


def _cutoff_for_delivery_date(delivery_date: date) -> datetime:
    """
    Return the purchasing-decision cutoff timestamp for a delivery date.

    Cutoff = (delivery_date − 1 day) at 09:20 UTC.
    January 2026 is in winter (GMT = UTC), so no DST adjustment applies.
    All timestamps are kept in UTC throughout.
    """
    day_before = delivery_date - timedelta(days=1)
    return datetime(
        day_before.year,
        day_before.month,
        day_before.day,
        CUTOFF_HOUR,
        CUTOFF_MINUTE,
        0,
        tzinfo=timezone.utc,
    )


# ── Parsers ──────────────────────────────────────────────────────────────────

def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string to a UTC-aware datetime."""
    if not value:
        return None
    try:
        dt = dateparser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a date string (YYYY-MM-DD) to date."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


# ── Raw → DataFrame helpers ──────────────────────────────────────────────────

def build_actuals_df(raw: list[dict]) -> pd.DataFrame:
    """
    Convert raw FUELHH WIND records to a clean DataFrame.

    Expected raw fields per record:
      settlementDate, settlementPeriod, generation, publishTime, fuelType

    Returns DataFrame with index-friendly columns and UTC-aware timestamps.
    Only fuelType==WIND records are retained (API should already filter but
    we double-check).
    """
    if not raw:
        logger.warning("No FUELHH records received; returning empty DataFrame.")
        return pd.DataFrame()

    df = pd.DataFrame(raw)

    # Keep only WIND records
    if "fuelType" in df.columns:
        df = df[df["fuelType"].str.upper() == "WIND"].copy()
    else:
        logger.warning("No fuelType column in FUELHH response.")

    required = {"settlementDate", "settlementPeriod", "generation"}
    missing = required - set(df.columns)
    if missing:
        logger.error("FUELHH response missing columns: %s", missing)
        return pd.DataFrame()

    df["settlementDate"] = df["settlementDate"].apply(_parse_date)
    df["settlementPeriod"] = pd.to_numeric(df["settlementPeriod"], errors="coerce")
    df["actual_mw"] = pd.to_numeric(df["generation"], errors="coerce")
    df["publishTime"] = df.get("publishTime", pd.Series([None] * len(df))).apply(
        _parse_ts
    )

    # Filter to January 2026
    jan_start = date(2026, 1, 1)
    jan_end = date(2026, 1, 31)
    df = df[
        df["settlementDate"].apply(lambda d: d is not None and jan_start <= d <= jan_end)
    ].copy()

    # Remove duplicates: keep the latest publishTime for each interval
    df = df.sort_values("publishTime", na_position="first")
    df = df.drop_duplicates(
        subset=["settlementDate", "settlementPeriod"], keep="last"
    )

    df = df.rename(columns={"settlementDate": "delivery_date", "settlementPeriod": "period"})
    df = df[["delivery_date", "period", "actual_mw", "publishTime"]].reset_index(drop=True)
    df = df.rename(columns={"publishTime": "actual_publish_time"})

    logger.info("Actuals DataFrame: %d intervals", len(df))
    return df


def build_forecasts_df(raw: list[dict]) -> pd.DataFrame:
    """
    Convert raw WINDFOR forecast records to a clean DataFrame.

    Expected raw fields per record:
      settlementDate, settlementPeriod, generation, publishTime, startTime

    Returns DataFrame with all available forecast vintages for January 2026
    delivery intervals. Does NOT apply the cutoff filter here — that is done
    in select_eligible_forecasts().
    """
    if not raw:
        logger.warning("No WINDFOR records received; returning empty DataFrame.")
        return pd.DataFrame()

    df = pd.DataFrame(raw)

    required = {"settlementDate", "settlementPeriod", "generation", "publishTime"}
    missing = required - set(df.columns)
    if missing:
        logger.error("WINDFOR response missing columns: %s", missing)
        return pd.DataFrame()

    df["settlementDate"] = df["settlementDate"].apply(_parse_date)
    df["settlementPeriod"] = pd.to_numeric(df["settlementPeriod"], errors="coerce")
    df["forecast_mw"] = pd.to_numeric(df["generation"], errors="coerce")
    df["publish_time"] = df["publishTime"].apply(_parse_ts)

    if "startTime" in df.columns:
        df["start_time"] = df["startTime"].apply(_parse_ts)
    else:
        df["start_time"] = None

    # Keep only January 2026 delivery intervals
    jan_start = date(2026, 1, 1)
    jan_end = date(2026, 1, 31)
    df = df[
        df["settlementDate"].apply(lambda d: d is not None and jan_start <= d <= jan_end)
    ].copy()

    df = df.rename(
        columns={"settlementDate": "delivery_date", "settlementPeriod": "period"}
    )
    df = df[["delivery_date", "period", "forecast_mw", "publish_time", "start_time"]].copy()

    # Drop records with unparseable publish_time (cannot determine eligibility)
    before = len(df)
    df = df.dropna(subset=["publish_time"]).copy()
    after = len(df)
    if before != after:
        logger.warning("Dropped %d WINDFOR records with null publishTime", before - after)

    logger.info("Forecasts DataFrame: %d records for Jan 2026 delivery", len(df))
    return df


def select_eligible_forecasts(forecasts_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each delivery interval (delivery_date, period), select the latest
    forecast whose publishTime is at or before the cutoff for that delivery date.

    Cutoff = (delivery_date − 1 day) at 09:20 UTC.

    Returns a DataFrame with one row per delivery interval, containing the
    selected forecast values. Intervals with no eligible forecast are NOT
    included (handled in merge_data).
    """
    if forecasts_df.empty:
        return pd.DataFrame()

    df = forecasts_df.copy()

    # Compute cutoff for each delivery date
    df["cutoff"] = df["delivery_date"].apply(_cutoff_for_delivery_date)

    # Keep only eligible forecasts
    eligible = df[df["publish_time"] <= df["cutoff"]].copy()

    if eligible.empty:
        logger.warning("No eligible forecasts found after cutoff filter.")
        return pd.DataFrame()

    # For each interval, pick the latest eligible forecast
    eligible = eligible.sort_values("publish_time")
    selected = eligible.groupby(["delivery_date", "period"], as_index=False).last()

    selected = selected.rename(
        columns={
            "forecast_mw": "eligible_forecast_mw",
            "publish_time": "eligible_publish_time",
            "start_time": "eligible_start_time",
            "cutoff": "cutoff_time",
        }
    )

    logger.info("Selected eligible forecasts: %d intervals", len(selected))
    return selected[
        ["delivery_date", "period", "eligible_forecast_mw", "eligible_publish_time",
         "eligible_start_time", "cutoff_time"]
    ]


def merge_data(actuals_df: pd.DataFrame, selected_df: pd.DataFrame) -> pd.DataFrame:
    """
    Outer-join actuals and selected forecasts on (delivery_date, period).

    Missing actuals or forecasts are preserved as NaN (NOT zero).
    Computes: signed_error, abs_error per interval.
    """
    if actuals_df.empty and selected_df.empty:
        return pd.DataFrame()

    # Ensure required columns exist even on empty DataFrames
    act = actuals_df.copy()
    if act.empty or "delivery_date" not in act.columns:
        act = pd.DataFrame(columns=["delivery_date", "period", "actual_mw", "actual_publish_time"])

    sel = selected_df.copy()
    if sel.empty or "delivery_date" not in sel.columns:
        sel = pd.DataFrame(columns=[
            "delivery_date", "period", "eligible_forecast_mw",
            "eligible_publish_time", "eligible_start_time", "cutoff_time"
        ])

    merged = pd.merge(
        act,
        sel,
        on=["delivery_date", "period"],
        how="outer",
    )

    # Compute errors only where both actual and forecast are present
    both_present = merged["actual_mw"].notna() & merged["eligible_forecast_mw"].notna()
    merged["signed_error_mw"] = np.where(
        both_present,
        merged["eligible_forecast_mw"] - merged["actual_mw"],
        np.nan,
    )
    merged["abs_error_mw"] = np.where(
        both_present,
        (merged["eligible_forecast_mw"] - merged["actual_mw"]).abs(),
        np.nan,
    )

    # Status flags
    merged["has_actual"] = merged["actual_mw"].notna()
    merged["has_forecast"] = merged["eligible_forecast_mw"].notna()
    merged["matched"] = both_present

    merged = merged.sort_values(["delivery_date", "period"]).reset_index(drop=True)
    logger.info(
        "Merged: %d total intervals, %d matched",
        len(merged),
        merged["matched"].sum(),
    )
    return merged


# ── Analytics ────────────────────────────────────────────────────────────────

def compute_summary(merged: pd.DataFrame) -> dict:
    """Compute January 2026 aggregate statistics."""
    matched = merged[merged["matched"]]
    n_matched = len(matched)

    mae = float(matched["abs_error_mw"].mean()) if n_matched > 0 else None
    rmse = (
        float(np.sqrt((matched["signed_error_mw"] ** 2).mean()))
        if n_matched > 0
        else None
    )
    mean_bias = float(matched["signed_error_mw"].mean()) if n_matched > 0 else None

    total_intervals = len(merged)
    coverage = round(n_matched / total_intervals * 100, 1) if total_intervals > 0 else 0.0

    return {
        "period_label": "January 2026",
        "analysis_note": (
            "Wind generation only (MW). "
            "Positive bias = overforecast. "
            "Percentage errors omitted — actual wind can be zero. "
            "This dataset contains no demand, price or thermal plant data."
        ),
        "matched_intervals": n_matched,
        "total_intervals": total_intervals,
        "coverage_pct": coverage,
        "mae_mw": round(mae, 1) if mae is not None else None,
        "rmse_mw": round(rmse, 1) if rmse is not None else None,
        "mean_bias_mw": round(mean_bias, 1) if mean_bias is not None else None,
        "cutoff_assumption": (
            f"Forecasts eligible if publishTime ≤ (delivery date − 1 day) "
            f"at {CUTOFF_HOUR:02d}:{CUTOFF_MINUTE:02d} UTC "
            "(EPEX SPOT GB day-ahead gate closure)"
        ),
        "timezone": "UTC throughout; January 2026 = GMT (no DST)",
    }


def compute_daily_summary(merged: pd.DataFrame) -> list[dict]:
    """Compute per-day analytics for the error chart."""
    rows = []
    for d, grp in merged.groupby("delivery_date"):
        matched = grp[grp["matched"]]
        n = len(matched)
        rows.append(
            {
                "date": str(d),
                "matched_intervals": n,
                "mae_mw": round(float(matched["abs_error_mw"].mean()), 1) if n > 0 else None,
                "rmse_mw": (
                    round(float(np.sqrt((matched["signed_error_mw"] ** 2).mean())), 1)
                    if n > 0
                    else None
                ),
                "mean_bias_mw": (
                    round(float(matched["signed_error_mw"].mean()), 1) if n > 0 else None
                ),
                "avg_actual_mw": (
                    round(float(matched["actual_mw"].mean()), 1) if n > 0 else None
                ),
                "avg_forecast_mw": (
                    round(float(matched["eligible_forecast_mw"].mean()), 1) if n > 0 else None
                ),
            }
        )
    return rows


def compute_data_quality(
    actuals_raw: list[dict],
    forecasts_raw: list[dict],
    merged: pd.DataFrame,
) -> dict:
    """Compute data quality / coverage metrics."""
    actual_count = len(actuals_raw)
    forecast_count = len(forecasts_raw)

    if merged.empty:
        return {
            "raw_actual_records": actual_count,
            "raw_forecast_records": forecast_count,
            "merged_intervals": 0,
            "matched_intervals": 0,
            "missing_actuals": 0,
            "missing_forecasts": 0,
            "unmatched_intervals": 0,
        }

    return {
        "raw_actual_records": actual_count,
        "raw_forecast_records": forecast_count,
        "merged_intervals": len(merged),
        "matched_intervals": int(merged["matched"].sum()),
        "missing_actuals": int((~merged["has_actual"]).sum()),
        "missing_forecasts": int((~merged["has_forecast"]).sum()),
        "unmatched_intervals": int((~merged["matched"]).sum()),
    }


def serialize_merged(merged: pd.DataFrame) -> list[dict]:
    """Convert merged DataFrame to JSON-serialisable list of dicts."""
    if merged.empty:
        return []
    df = merged.copy()
    for col in ["delivery_date"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)
    for col in ["actual_publish_time", "eligible_publish_time",
                "eligible_start_time", "cutoff_time"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x.isoformat() if isinstance(x, datetime) else None
            )
    for col in ["actual_mw", "eligible_forecast_mw", "signed_error_mw", "abs_error_mw"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: round(float(x), 2) if pd.notna(x) else None)
    for col in ["period"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notna(x) else None)
    for col in ["has_actual", "has_forecast", "matched"]:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df.to_dict(orient="records")


def get_forecast_history(
    forecasts_df: pd.DataFrame,
    delivery_date: date,
    period: int,
    cutoff_hour: int = CUTOFF_HOUR,
    cutoff_minute: int = CUTOFF_MINUTE,
) -> list[dict]:
    """
    Return all forecast vintages for a specific delivery interval.
    Marks each as eligible or published-too-late relative to the cutoff.
    """
    if forecasts_df.empty:
        return []

    cutoff = _cutoff_for_delivery_date(delivery_date)
    mask = (
        (forecasts_df["delivery_date"] == delivery_date)
        & (forecasts_df["period"] == period)
    )
    subset = forecasts_df[mask].copy()

    records = []
    for _, row in subset.sort_values("publish_time").iterrows():
        pt = row["publish_time"]
        eligible = bool(pt <= cutoff) if pt is not None else False
        records.append(
            {
                "publish_time": pt.isoformat() if pt else None,
                "forecast_mw": round(float(row["forecast_mw"]), 2) if pd.notna(row["forecast_mw"]) else None,
                "eligible": eligible,
                "cutoff_time": cutoff.isoformat(),
                "delivery_date": str(delivery_date),
                "period": int(period),
            }
        )
    return records
