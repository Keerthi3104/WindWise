"""
WindWise Backend — FastAPI application entry point.

API endpoints:
  GET /api/health            — Health check
  GET /api/summary           — January 2026 aggregate metrics
  GET /api/forecast-actuals  — Interval-level forecast vs actual data
  GET /api/forecast-history  — Forecast publication history for one interval
  GET /api/data-quality      — Data quality / coverage statistics
  POST /api/refresh          — Force cache refresh

Interactive API docs available at /docs (Swagger UI).
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import io
import csv

from app.config import settings
from app.cache import get_cache
from app.elexon_client import fetch_fuelhh_wind_actuals, fetch_windfor_forecasts
from app.data_processor import (
    build_actuals_df,
    build_forecasts_df,
    select_eligible_forecasts,
    merge_data,
    compute_summary,
    compute_daily_summary,
    compute_data_quality,
    serialize_merged,
    get_forecast_history,
    CUTOFF_HOUR,
    CUTOFF_MINUTE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WindWise API starting up …")
    asyncio.create_task(ensure_data_loaded())
    yield

app = FastAPI(
    title="WindWise API",
    description=(
        "Wind generation forecast accuracy analytics for January 2026. "
        "Data source: Elexon BMRS (FUELHH WIND actuals + WINDFOR forecasts). "
        "Forecast cutoff: EPEX SPOT GB day-ahead gate closure (D-1 at 09:20 UTC)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Data loading ─────────────────────────────────────────────────────────────

_fetch_lock = asyncio.Lock()


async def ensure_data_loaded(force: bool = False):
    """Load and process data into cache if not already fresh."""
    cache = get_cache()
    if not force and cache.is_fresh():
        return

    async with _fetch_lock:
        # Double-check after acquiring lock
        if not force and cache.is_fresh():
            return

        logger.info("Loading data from Elexon BMRS …")
        try:
            actuals_raw, forecasts_raw = await asyncio.gather(
                fetch_fuelhh_wind_actuals(),
                fetch_windfor_forecasts(),
            )
        except Exception as exc:
            msg = f"API fetch failed: {exc}"
            logger.error(msg)
            cache.set_error(msg)
            raise HTTPException(status_code=502, detail=msg)

        try:
            actuals_df = build_actuals_df(actuals_raw)
            forecasts_df = build_forecasts_df(forecasts_raw)
            selected_df = select_eligible_forecasts(forecasts_df)
            merged_df = merge_data(actuals_df, selected_df)
        except Exception as exc:
            msg = f"Data processing failed: {exc}"
            logger.error(msg, exc_info=True)
            cache.set_error(msg)
            raise HTTPException(status_code=500, detail=msg)

        cache.store(actuals_raw, forecasts_raw, actuals_df, forecasts_df, merged_df)
        logger.info("Data loaded and cached successfully.")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health():
    """Health check endpoint."""
    cache = get_cache()
    return {
        "status": "ok",
        "service": "WindWise API",
        "version": "1.0.0",
        "cache_fresh": cache.is_fresh(),
        "last_error": cache.last_error,
        "last_fetch_time": (
            datetime.fromtimestamp(cache.last_fetch_time, tz=timezone.utc).isoformat()
            if cache.last_fetch_time
            else None
        ),
        "cutoff": f"D-1 at {CUTOFF_HOUR:02d}:{CUTOFF_MINUTE:02d} UTC (EPEX SPOT GB day-ahead gate closure)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/summary", tags=["Analytics"])
async def summary():
    """
    January 2026 aggregate forecast accuracy metrics.

    Returns MAE, RMSE, mean bias, coverage, and matched interval count.
    Metrics cover WIND generation only (MW). Positive bias = overforecast.
    """
    await ensure_data_loaded()
    cache = get_cache()
    _, _, _, _, merged_df = cache.get()

    if merged_df.empty:
        raise HTTPException(status_code=503, detail="No data available.")

    result = compute_summary(merged_df)
    daily = compute_daily_summary(merged_df)
    result["daily_summaries"] = daily
    return result


@app.get("/api/forecast-actuals", tags=["Analytics"])
async def forecast_actuals(
    date_from: Optional[str] = Query(None, description="Filter from date YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="Filter to date YYYY-MM-DD (inclusive)"),
    period: Optional[int] = Query(None, ge=1, le=50, description="Settlement period 1-50"),
    matched_only: bool = Query(False, description="Return only matched intervals"),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """
    Interval-level actual vs forecast data for January 2026.

    Each record contains: delivery_date, period, actual_mw, eligible_forecast_mw,
    signed_error_mw, abs_error_mw, eligible_publish_time, cutoff_time, matched flag.

    signed_error = forecast − actual (positive = overforecast).
    Missing actuals or forecasts are returned as null, NOT zero.
    """
    await ensure_data_loaded()
    cache = get_cache()
    _, _, _, _, merged_df = cache.get()

    if merged_df.empty:
        return {"data": [], "total": 0, "offset": offset, "limit": limit}

    df = merged_df.copy()

    # Date filters
    if date_from:
        try:
            d = date.fromisoformat(date_from)
            df = df[df["delivery_date"] >= d]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format (YYYY-MM-DD)")
    if date_to:
        try:
            d = date.fromisoformat(date_to)
            df = df[df["delivery_date"] <= d]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format (YYYY-MM-DD)")
    if period is not None:
        df = df[df["period"] == period]
    if matched_only:
        df = df[df["matched"]]

    total = len(df)
    df = df.iloc[offset : offset + limit]
    records = serialize_merged(df)

    return {"data": records, "total": total, "offset": offset, "limit": limit}


@app.get("/api/forecast-history", tags=["Analytics"])
async def forecast_history(
    delivery_date: str = Query(..., description="Delivery date YYYY-MM-DD"),
    period: int = Query(..., ge=1, le=50, description="Settlement period 1-50"),
):
    """
    All forecast publication vintages for a specific delivery interval.

    Returns every WINDFOR record for the given (delivery_date, period),
    marking each as 'eligible' (publishTime ≤ cutoff) or published too late.
    Also returns the actual generation value for that interval if available.
    """
    try:
        d = date.fromisoformat(delivery_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid delivery_date (YYYY-MM-DD)")

    if not (date(2026, 1, 1) <= d <= date(2026, 1, 31)):
        raise HTTPException(status_code=400, detail="delivery_date must be in January 2026")

    await ensure_data_loaded()
    cache = get_cache()
    _, _, actuals_df, forecasts_df, merged_df = cache.get()

    history = get_forecast_history(forecasts_df, d, period)

    # Get actual for this interval
    actual_mw = None
    if not actuals_df.empty:
        mask = (actuals_df["delivery_date"] == d) & (actuals_df["period"] == period)
        row = actuals_df[mask]
        if not row.empty:
            v = row["actual_mw"].iloc[0]
            actual_mw = round(float(v), 2) if pd.notna(v) else None

    return {
        "delivery_date": delivery_date,
        "period": period,
        "actual_mw": actual_mw,
        "forecast_vintages": history,
        "total_vintages": len(history),
        "eligible_count": sum(1 for r in history if r["eligible"]),
        "cutoff_assumption": (
            f"D-1 at {CUTOFF_HOUR:02d}:{CUTOFF_MINUTE:02d} UTC "
            "(EPEX SPOT GB day-ahead gate closure)"
        ),
    }


@app.get("/api/data-quality", tags=["Analytics"])
async def data_quality():
    """
    Data quality statistics: record counts, coverage, missing values,
    unmatched intervals, last fetch time, and any API errors.
    """
    cache = get_cache()

    # Try to load if not fresh — but don't fail hard
    try:
        await ensure_data_loaded()
    except HTTPException as exc:
        return {
            "status": "error",
            "error": exc.detail,
            "cache_fresh": False,
            "last_fetch_time": None,
        }

    actuals_raw, forecasts_raw, _, _, merged_df = cache.get()
    quality = compute_data_quality(actuals_raw, forecasts_raw, merged_df)
    quality["status"] = "ok"
    quality["last_fetch_time"] = (
        datetime.fromtimestamp(cache.last_fetch_time, tz=timezone.utc).isoformat()
        if cache.last_fetch_time
        else None
    )
    quality["last_error"] = cache.last_error
    quality["cache_ttl_seconds"] = settings.cache_ttl
    return quality


@app.post("/api/refresh", tags=["System"])
async def refresh_data(background_tasks: BackgroundTasks):
    """
    Force a cache refresh from the Elexon API.
    Triggers a background reload and returns immediately.
    """
    async def _do_refresh():
        try:
            await ensure_data_loaded(force=True)
        except Exception as exc:
            logger.error("Background refresh failed: %s", exc)

    background_tasks.add_task(_do_refresh)
    return {"message": "Data refresh triggered. Check /api/data-quality for status."}


@app.get("/api/export/csv", tags=["Export"])
async def export_csv():
    """
    Export the full matched dataset as a CSV file.
    Includes: delivery_date, period, actual_mw, eligible_forecast_mw,
    signed_error_mw, abs_error_mw, eligible_publish_time, cutoff_time.
    """
    await ensure_data_loaded()
    cache = get_cache()
    _, _, _, _, merged_df = cache.get()

    if merged_df.empty:
        raise HTTPException(status_code=503, detail="No data available for export.")

    records = serialize_merged(merged_df)
    if not records:
        raise HTTPException(status_code=503, detail="No records to export.")

    fieldnames = list(records[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=windwise_jan2026.csv"},
    )



