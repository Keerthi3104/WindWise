"""
WindWise Backend — Unit and integration tests.
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pandas as pd
import numpy as np

from app.data_processor import (
    build_actuals_df,
    build_forecasts_df,
    select_eligible_forecasts,
    merge_data,
    compute_summary,
    compute_daily_summary,
    compute_data_quality,
    get_forecast_history,
    _cutoff_for_delivery_date,
    _parse_ts,
    CUTOFF_HOUR,
    CUTOFF_MINUTE,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_actual(settlement_date="2026-01-15", period=1, generation=1000.0,
                publish_time="2026-01-16T00:00:00Z"):
    return {
        "dataset": "FUELHH",
        "settlementDate": settlement_date,
        "settlementPeriod": period,
        "fuelType": "WIND",
        "generation": generation,
        "publishTime": publish_time,
    }


def make_forecast(settlement_date="2026-01-15", period=1, generation=1100.0,
                  publish_time="2026-01-14T08:00:00Z", start_time="2026-01-15T00:00:00Z"):
    return {
        "dataset": "WINDFOR",
        "settlementDate": settlement_date,
        "settlementPeriod": period,
        "generation": generation,
        "publishTime": publish_time,
        "startTime": start_time,
    }


def make_real_windfor(start_time="2026-01-15T08:00:00Z", generation=12500.0,
                      publish_time="2026-01-14T07:30:00Z"):
    """Representative real Elexon BMRS WINDFOR/stream item (no settlementDate/Period)."""
    return {
        "dataset": "WINDFOR",
        "startTime": start_time,
        "publishTime": publish_time,
        "generation": generation,
    }


# ── Cutoff tests ──────────────────────────────────────────────────────────────

class TestCutoff:
    def test_cutoff_is_day_before(self):
        d = date(2026, 1, 15)
        cutoff = _cutoff_for_delivery_date(d)
        assert cutoff.date() == date(2026, 1, 14)
        assert cutoff.hour == CUTOFF_HOUR
        assert cutoff.minute == CUTOFF_MINUTE
        assert cutoff.tzinfo == timezone.utc

    def test_cutoff_jan_1(self):
        d = date(2026, 1, 1)
        cutoff = _cutoff_for_delivery_date(d)
        assert cutoff.date() == date(2025, 12, 31)

    def test_cutoff_jan_31(self):
        d = date(2026, 1, 31)
        cutoff = _cutoff_for_delivery_date(d)
        assert cutoff.date() == date(2026, 1, 30)


# ── Timestamp parser tests ────────────────────────────────────────────────────

class TestParseTs:
    def test_parse_z_suffix(self):
        dt = _parse_ts("2026-01-15T08:00:00Z")
        assert dt is not None
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 8

    def test_parse_offset(self):
        dt = _parse_ts("2026-01-15T08:00:00+00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc

    def test_parse_none(self):
        assert _parse_ts(None) is None

    def test_parse_invalid(self):
        assert _parse_ts("not-a-date") is None


# ── Actuals DataFrame tests ───────────────────────────────────────────────────

class TestBuildActualsDF:
    def test_basic(self):
        raw = [make_actual()]
        df = build_actuals_df(raw)
        assert len(df) == 1
        assert df["actual_mw"].iloc[0] == 1000.0

    def test_filters_non_wind(self):
        raw = [make_actual(), {"settlementDate": "2026-01-15", "settlementPeriod": 1,
                               "fuelType": "CCGT", "generation": 5000, "publishTime": "2026-01-16T00:00:00Z"}]
        df = build_actuals_df(raw)
        assert len(df) == 1

    def test_out_of_range_filtered(self):
        raw = [make_actual(settlement_date="2025-12-31")]
        df = build_actuals_df(raw)
        assert len(df) == 0

    def test_empty_input(self):
        df = build_actuals_df([])
        assert df.empty

    def test_deduplication_keeps_latest(self):
        raw = [
            make_actual(period=1, generation=1000, publish_time="2026-01-16T00:00:00Z"),
            make_actual(period=1, generation=1200, publish_time="2026-01-16T01:00:00Z"),
        ]
        df = build_actuals_df(raw)
        assert len(df) == 1
        assert df["actual_mw"].iloc[0] == 1200.0


# ── Forecasts DataFrame tests ─────────────────────────────────────────────────

class TestBuildForecastsDF:
    def test_basic(self):
        raw = [make_forecast()]
        df = build_forecasts_df(raw)
        assert len(df) == 1
        assert df["forecast_mw"].iloc[0] == 1100.0

    def test_empty(self):
        df = build_forecasts_df([])
        assert df.empty

    def test_out_of_jan_filtered(self):
        raw = [make_forecast(settlement_date="2025-12-15")]
        df = build_forecasts_df(raw)
        assert len(df) == 0

    def test_null_publish_time_dropped(self):
        raw = [make_forecast(publish_time=None)]
        # Should drop nulls
        df = build_forecasts_df(raw)
        assert len(df) == 0


# ── Eligible forecast selection tests ────────────────────────────────────────

class TestSelectEligibleForecasts:
    def _make_df(self, records):
        raw = [make_forecast(**r) for r in records]
        return build_forecasts_df(raw)

    def test_selects_latest_before_cutoff(self):
        # Cutoff for 2026-01-15 = 2026-01-14 09:20 UTC
        records = [
            {"publish_time": "2026-01-14T06:00:00Z", "generation": 900.0},
            {"publish_time": "2026-01-14T08:00:00Z", "generation": 1000.0},  # latest eligible
            {"publish_time": "2026-01-14T10:00:00Z", "generation": 1100.0},  # too late
        ]
        raw = []
        for r in records:
            raw.append(make_forecast(
                settlement_date="2026-01-15",
                period=1,
                generation=r["generation"],
                publish_time=r["publish_time"],
            ))
        df = build_forecasts_df(raw)
        selected = select_eligible_forecasts(df)
        assert len(selected) == 1
        assert selected["eligible_forecast_mw"].iloc[0] == 1000.0

    def test_no_eligible_returns_empty(self):
        # All published after cutoff
        raw = [make_forecast(publish_time="2026-01-14T12:00:00Z")]  # after 09:20
        df = build_forecasts_df(raw)
        selected = select_eligible_forecasts(df)
        assert selected.empty

    def test_exactly_at_cutoff_is_eligible(self):
        # publishTime == cutoff should be eligible (<=)
        pub_time = f"2026-01-14T{CUTOFF_HOUR:02d}:{CUTOFF_MINUTE:02d}:00Z"
        raw = [make_forecast(publish_time=pub_time)]
        df = build_forecasts_df(raw)
        selected = select_eligible_forecasts(df)
        assert len(selected) == 1


# ── Merge tests ───────────────────────────────────────────────────────────────

class TestMergeData:
    def test_matched_interval(self):
        actuals_raw = [make_actual(generation=1000.0)]
        forecasts_raw = [make_forecast(generation=1100.0)]
        actuals_df = build_actuals_df(actuals_raw)
        forecasts_df = build_forecasts_df(forecasts_raw)
        selected_df = select_eligible_forecasts(forecasts_df)
        merged = merge_data(actuals_df, selected_df)

        row = merged.iloc[0]
        assert row["matched"]
        assert row["actual_mw"] == 1000.0
        assert row["eligible_forecast_mw"] == 1100.0
        assert abs(row["signed_error_mw"] - 100.0) < 0.01
        assert abs(row["abs_error_mw"] - 100.0) < 0.01

    def test_missing_actual_is_nan_not_zero(self):
        # No actual provided; only forecast
        forecasts_raw = [make_forecast(generation=1100.0)]
        forecasts_df = build_forecasts_df(forecasts_raw)
        selected_df = select_eligible_forecasts(forecasts_df)
        actuals_df = pd.DataFrame()
        merged = merge_data(actuals_df, selected_df)
        if not merged.empty:
            row = merged.iloc[0]
            assert pd.isna(row["actual_mw"]) or row["actual_mw"] != 0

    def test_positive_bias_means_overforecast(self):
        actuals_raw = [make_actual(generation=500.0)]
        forecasts_raw = [make_forecast(generation=700.0)]
        actuals_df = build_actuals_df(actuals_raw)
        forecasts_df = build_forecasts_df(forecasts_raw)
        selected_df = select_eligible_forecasts(forecasts_df)
        merged = merge_data(actuals_df, selected_df)
        assert merged["signed_error_mw"].iloc[0] > 0  # overforecast

    def test_negative_bias_means_underforecast(self):
        actuals_raw = [make_actual(generation=700.0)]
        forecasts_raw = [make_forecast(generation=500.0)]
        actuals_df = build_actuals_df(actuals_raw)
        forecasts_df = build_forecasts_df(forecasts_raw)
        selected_df = select_eligible_forecasts(forecasts_df)
        merged = merge_data(actuals_df, selected_df)
        assert merged["signed_error_mw"].iloc[0] < 0  # underforecast


# ── Summary stats tests ───────────────────────────────────────────────────────

class TestComputeSummary:
    def _make_merged(self):
        rows = []
        for i, (actual, forecast) in enumerate([(1000, 1100), (2000, 1800), (500, 500)]):
            rows.append({
                "delivery_date": date(2026, 1, 15),
                "period": i + 1,
                "actual_mw": actual,
                "eligible_forecast_mw": forecast,
                "signed_error_mw": forecast - actual,
                "abs_error_mw": abs(forecast - actual),
                "has_actual": True,
                "has_forecast": True,
                "matched": True,
                "actual_publish_time": None,
                "eligible_publish_time": None,
                "eligible_start_time": None,
                "cutoff_time": None,
            })
        return pd.DataFrame(rows)

    def test_mae_correct(self):
        merged = self._make_merged()
        summary = compute_summary(merged)
        # errors: 100, -200, 0 → abs: 100, 200, 0 → MAE = 100
        assert summary["mae_mw"] == 100.0

    def test_rmse_correct(self):
        merged = self._make_merged()
        summary = compute_summary(merged)
        expected = np.sqrt((100**2 + 200**2 + 0**2) / 3)
        assert abs(summary["rmse_mw"] - expected) < 0.5

    def test_mean_bias(self):
        merged = self._make_merged()
        summary = compute_summary(merged)
        # (100 - 200 + 0) / 3 = -100/3 ≈ -33.3
        assert abs(summary["mean_bias_mw"] - (-100 / 3)) < 0.5

    def test_coverage(self):
        merged = self._make_merged()
        summary = compute_summary(merged)
        assert summary["coverage_pct"] == 100.0


# ── Forecast history tests ────────────────────────────────────────────────────

class TestForecastHistory:
    def test_marks_eligible_and_too_late(self):
        raw = [
            make_forecast(settlement_date="2026-01-15", period=1,
                          generation=900.0, publish_time="2026-01-14T08:00:00Z"),
            make_forecast(settlement_date="2026-01-15", period=1,
                          generation=1100.0, publish_time="2026-01-14T11:00:00Z"),
        ]
        forecasts_df = build_forecasts_df(raw)
        history = get_forecast_history(forecasts_df, date(2026, 1, 15), 1)
        eligible = [r for r in history if r["eligible"]]
        not_eligible = [r for r in history if not r["eligible"]]
        assert len(eligible) == 1
        assert abs(eligible[0]["forecast_mw"] - 900.0) < 0.01
        assert len(not_eligible) == 1
        assert abs(not_eligible[0]["forecast_mw"] - 1100.0) < 0.01


# ── Regression tests for real Elexon WINDFOR stream schema ────────────────────

class TestRealWindforSchema:
    def test_hourly_forecast_expands_to_two_periods(self):
        # Hourly forecast at 08:00 UTC covers SP17 (08:00-08:30) and SP18 (08:30-09:00)
        raw = [make_real_windfor(start_time="2026-01-15T08:00:00Z", generation=12500.0)]
        df = build_forecasts_df(raw)
        assert len(df) == 2
        periods = sorted(df["period"].tolist())
        assert periods == [17, 18]
        assert df["forecast_mw"].tolist() == [12500.0, 12500.0]
        assert df["delivery_date"].iloc[0] == date(2026, 1, 15)

    def test_half_hourly_forecast_maps_to_single_period(self):
        # Forecast with startTime at 08:30 UTC maps to SP18 (8*2 + 2)
        raw = [make_real_windfor(start_time="2026-01-15T08:30:00Z", generation=13000.0)]
        df = build_forecasts_df(raw)
        assert len(df) == 1
        assert df["period"].iloc[0] == 18
        assert df["forecast_mw"].iloc[0] == 13000.0

    def test_cutoff_strict_boundary(self):
        # Delivery date 2026-01-15: cutoff is 2026-01-14 09:20:00 UTC
        raw = [
            # Published before cutoff: eligible
            make_real_windfor(publish_time="2026-01-14T07:30:00Z", generation=10000.0),
            # Exactly at cutoff: eligible
            make_real_windfor(publish_time="2026-01-14T09:20:00Z", generation=11000.0),
            # After cutoff: ineligible (too late)
            make_real_windfor(publish_time="2026-01-14T09:30:00Z", generation=12000.0),
            make_real_windfor(publish_time="2026-01-15T02:30:00Z", generation=13000.0),
        ]
        df = build_forecasts_df(raw)
        selected = select_eligible_forecasts(df)
        assert len(selected) == 2  # SP17 and SP18
        # Should pick the 09:20:00Z forecast (latest eligible before cutoff)
        row_sp17 = selected[selected["period"] == 17].iloc[0]
        assert row_sp17["eligible_forecast_mw"] == 11000.0
        assert row_sp17["eligible_publish_time"] == datetime(2026, 1, 14, 9, 20, tzinfo=timezone.utc)

    def test_end_to_end_matching_with_fuelhh(self):
        # Real WINDFOR stream record matched with real FUELHH record
        windfor_raw = [
            make_real_windfor(start_time="2026-01-15T08:00:00Z", generation=12000.0,
                              publish_time="2026-01-14T07:30:00Z"),
        ]
        fuelhh_raw = [
            make_actual(settlement_date="2026-01-15", period=17, generation=10000.0),
            make_actual(settlement_date="2026-01-15", period=18, generation=11000.0),
        ]
        df_act = build_actuals_df(fuelhh_raw)
        df_fc = build_forecasts_df(windfor_raw)
        df_sel = select_eligible_forecasts(df_fc)
        merged = merge_data(df_act, df_sel)

        assert len(merged) == 2
        assert merged["matched"].all()

        row17 = merged[merged["period"] == 17].iloc[0]
        assert row17["actual_mw"] == 10000.0
        assert row17["eligible_forecast_mw"] == 12000.0
        assert row17["signed_error_mw"] == 2000.0  # Overforecast (+2000)
        assert row17["abs_error_mw"] == 2000.0

        row18 = merged[merged["period"] == 18].iloc[0]
        assert row18["actual_mw"] == 11000.0
        assert row18["eligible_forecast_mw"] == 12000.0
        assert row18["signed_error_mw"] == 1000.0
        assert row18["abs_error_mw"] == 1000.0

    def test_out_of_january_records_excluded(self):
        raw = [
            make_real_windfor(start_time="2025-12-31T23:00:00Z"),
            make_real_windfor(start_time="2026-02-01T00:00:00Z"),
        ]
        df = build_forecasts_df(raw)
        assert df.empty

    def test_corrupt_records_rejected_safely(self):
        raw = [
            {"dataset": "WINDFOR"},  # Missing all required
            {"dataset": "WINDFOR", "startTime": "invalid-date", "generation": 100, "publishTime": "2026-01-01T00:00:00Z"},
            {"dataset": "WINDFOR", "startTime": "2026-01-15T08:00:00Z", "generation": "not-a-number", "publishTime": "2026-01-01T00:00:00Z"},
            {"dataset": "WINDFOR", "startTime": "2026-01-15T08:00:00Z", "generation": 1000, "publishTime": None},
        ]
        df = build_forecasts_df(raw)
        assert df.empty

