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
      settlementDate, settlementPeriod, generation, publishTime, fuelType, startTime
    Only fuelType==WIND records are retained.
    """
    if not raw:
        logger.warning("No FUELHH records received; returning empty DataFrame.")
        return pd.DataFrame()

    # Diagnostic logging: sample keys and safely truncated record
    sample_keys = list(raw[0].keys())
    safe_sample = {k: str(raw[0][k])[:50] for k in sample_keys}
    logger.info("FUELHH raw stream inspection: count=%d, keys=%s, sample=%s", len(raw), sample_keys, safe_sample)

    jan_start = date(2026, 1, 1)
    jan_end = date(2026, 1, 31)

    parsed_rows = []
    skipped_fuel = 0
    skipped_gen = 0
    skipped_time = 0
    skipped_out_of_range = 0

    for item in raw:
        fuel = str(item.get("fuelType", "")).upper()
        if fuel and fuel != "WIND":
            skipped_fuel += 1
            continue

        gen = item.get("generation")
        if gen is None:
            skipped_gen += 1
            continue
        try:
            gen_val = float(gen)
        except (ValueError, TypeError):
            skipped_gen += 1
            continue

        pub_time = _parse_ts(item.get("publishTime"))

        # Determine delivery_date and period
        deliv_date = _parse_date(item.get("settlementDate"))
        period_raw = item.get("settlementPeriod")
        period_val = None
        if period_raw is not None:
            try:
                period_val = int(period_raw)
            except (ValueError, TypeError):
                pass

        # Fallback to startTime if needed
        if (not deliv_date or period_val is None) and "startTime" in item:
            st = _parse_ts(item.get("startTime"))
            if st:
                if not deliv_date:
                    deliv_date = st.date()
                if period_val is None:
                    period_val = st.hour * 2 + (st.minute // 30) + 1

        if not deliv_date or period_val is None or not (1 <= period_val <= 50):
            skipped_time += 1
            continue

        if not (jan_start <= deliv_date <= jan_end):
            skipped_out_of_range += 1
            continue

        parsed_rows.append({
            "delivery_date": deliv_date,
            "period": period_val,
            "actual_mw": gen_val,
            "actual_publish_time": pub_time,
        })

    if not parsed_rows:
        logger.warning(
            "FUELHH parsing resulted in 0 rows. Dropped: non_wind=%d, gen=%d, time=%d, out_of_range=%d",
            skipped_fuel, skipped_gen, skipped_time, skipped_out_of_range
        )
        return pd.DataFrame()

    df = pd.DataFrame(parsed_rows)
    # Deduplication: keep latest publishTime for each interval
    df = df.sort_values("actual_publish_time", na_position="first")
    df = df.drop_duplicates(subset=["delivery_date", "period"], keep="last")
    df = df.sort_values(["delivery_date", "period"]).reset_index(drop=True)

    logger.info(
        "FUELHH actuals parsed successfully: raw=%d -> unique_intervals=%d (Jan 2026). Filtered non_wind=%d",
        len(raw), len(df), skipped_fuel
    )
    return df


def build_forecasts_df(raw: list[dict]) -> pd.DataFrame:
    """
    Convert raw WINDFOR forecast records to a clean DataFrame.

    Real Elexon BMRS WINDFOR stream response schema:
      {'dataset': 'WINDFOR', 'publishTime': '...', 'startTime': '...', 'generation': ...}
    Does NOT contain 'settlementDate' or 'settlementPeriod'.
    - 'startTime' is an hourly ISO timestamp (e.g., '2026-01-15T08:00:00Z').
    - Each 1-hour forecast applies to two half-hour settlement periods:
      SP 2*H + 1 (e.g. 08:00 -> SP 17) and SP 2*H + 2 (e.g. 08:30 -> SP 18).
    - If a record explicitly provides 'settlementDate' and 'settlementPeriod',
      those are respected directly.
    - Preserves all forecast vintages published for January 2026 delivery intervals.
    """
    if not raw:
        logger.warning("No WINDFOR records received; returning empty DataFrame.")
        return pd.DataFrame()

    # Diagnostic logging: sample keys and safely truncated record
    sample_keys = list(raw[0].keys())
    safe_sample = {k: str(raw[0][k])[:50] for k in sample_keys}
    logger.info("WINDFOR raw stream inspection: count=%d, keys=%s, sample=%s", len(raw), sample_keys, safe_sample)

    jan_start = date(2026, 1, 1)
    jan_end = date(2026, 1, 31)

    parsed_rows = []
    skipped_gen = 0
    skipped_pub = 0
    skipped_time = 0
    skipped_out_of_range = 0

    for item in raw:
        gen = item.get("generation")
        if gen is None:
            skipped_gen += 1
            continue
        try:
            gen_val = float(gen)
        except (ValueError, TypeError):
            skipped_gen += 1
            continue

        pub_time = _parse_ts(item.get("publishTime"))
        if not pub_time:
            skipped_pub += 1
            continue

        # Case 1: Record explicitly contains settlementDate & settlementPeriod
        if "settlementDate" in item and "settlementPeriod" in item:
            deliv_date = _parse_date(item.get("settlementDate"))
            period_raw = item.get("settlementPeriod")
            try:
                period_val = int(period_raw)
            except (ValueError, TypeError):
                period_val = None

            if not deliv_date or period_val is None or not (1 <= period_val <= 50):
                skipped_time += 1
                continue

            if not (jan_start <= deliv_date <= jan_end):
                skipped_out_of_range += 1
                continue

            st = _parse_ts(item.get("startTime")) if "startTime" in item else None
            parsed_rows.append({
                "delivery_date": deliv_date,
                "period": period_val,
                "forecast_mw": gen_val,
                "publish_time": pub_time,
                "start_time": st,
            })
            continue

        # Case 2: Record contains startTime (standard WINDFOR stream format)
        st_raw = item.get("startTime")
        if not st_raw:
            skipped_time += 1
            continue

        st = _parse_ts(st_raw)
        if not st:
            skipped_time += 1
            continue

        deliv_date = st.date()
        if not (jan_start <= deliv_date <= jan_end):
            skipped_out_of_range += 1
            continue

        hour = st.hour
        minute = st.minute

        # National Grid ESO WINDFOR hourly forecasts (minute == 0)
        # 1 hour covers two half-hour settlement periods (SP 2*H + 1 and SP 2*H + 2)
        if minute == 0:
            sp1 = hour * 2 + 1
            sp2 = hour * 2 + 2
            for sp in (sp1, sp2):
                parsed_rows.append({
                    "delivery_date": deliv_date,
                    "period": sp,
                    "forecast_mw": gen_val,
                    "publish_time": pub_time,
                    "start_time": st,
                })
        elif minute == 30:
            sp = hour * 2 + 2
            parsed_rows.append({
                "delivery_date": deliv_date,
                "period": sp,
                "forecast_mw": gen_val,
                "publish_time": pub_time,
                "start_time": st,
            })
        else:
            sp = min(48, max(1, hour * 2 + (minute // 30) + 1))
            parsed_rows.append({
                "delivery_date": deliv_date,
                "period": sp,
                "forecast_mw": gen_val,
                "publish_time": pub_time,
                "start_time": st,
            })

    if not parsed_rows:
        logger.warning(
            "WINDFOR parsing resulted in 0 rows. Rejections: gen=%d, pub=%d, time=%d, out_of_range=%d",
            skipped_gen, skipped_pub, skipped_time, skipped_out_of_range
        )
        return pd.DataFrame()

    df = pd.DataFrame(parsed_rows)

    # Deterministic deduplication: if multiple identical (delivery_date, period, publish_time) rows exist, keep last
    df = df.sort_values("publish_time", na_position="first")
    df = df.drop_duplicates(subset=["delivery_date", "period", "publish_time"], keep="last")

    logger.info(
        "WINDFOR parsed successfully: raw=%d -> valid_intervals=%d (Jan 2026). Dropped: gen=%d, pub=%d, time=%d, out_of_range=%d",
        len(raw), len(df), skipped_gen, skipped_pub, skipped_time, skipped_out_of_range
    )
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
        logger.warning("select_eligible_forecasts called with empty forecasts_df")
        return pd.DataFrame()

    df = forecasts_df.copy()

    # Compute cutoff for each delivery date
    df["cutoff"] = df["delivery_date"].apply(_cutoff_for_delivery_date)

    # Keep only eligible forecasts
    eligible = df[df["publish_time"] <= df["cutoff"]].copy()

    logger.info(
        "Cutoff evaluation (D-1 %02d:%02d UTC): total_vintages=%d, eligible_vintages=%d, post_cutoff_vintages=%d",
        CUTOFF_HOUR, CUTOFF_MINUTE, len(df), len(eligible), len(df) - len(eligible)
    )

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

    logger.info("Selected latest eligible forecast for %d unique intervals", len(selected))
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
    n_act = int(merged["has_actual"].sum())
    n_fc = int(merged["has_forecast"].sum())
    n_match = int(merged["matched"].sum())
    logger.info(
        "Merged data summary: total_intervals=%d, actuals_present=%d, forecasts_present=%d, matched_pairs=%d",
        len(merged), n_act, n_fc, n_match
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
    subset = subset.sort_values("publish_time").drop_duplicates(subset=["publish_time"], keep="last")
    for _, row in subset.iterrows():
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
