"""
WindWise Backend — FastAPI endpoint tests.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def mock_cache_data():
    """Provide a minimal merged DataFrame for endpoint tests."""
    import pandas as pd
    import numpy as np
    from datetime import date, datetime, timezone

    rows = []
    for period in range(1, 5):
        rows.append({
            "delivery_date": date(2026, 1, 15),
            "period": period,
            "actual_mw": 1000.0,
            "eligible_forecast_mw": 1100.0,
            "signed_error_mw": 100.0,
            "abs_error_mw": 100.0,
            "has_actual": True,
            "has_forecast": True,
            "matched": True,
            "actual_publish_time": datetime(2026, 1, 16, 0, 0, 0, tzinfo=timezone.utc),
            "eligible_publish_time": datetime(2026, 1, 14, 8, 0, 0, tzinfo=timezone.utc),
            "eligible_start_time": None,
            "cutoff_time": datetime(2026, 1, 14, 9, 20, 0, tzinfo=timezone.utc),
        })
    return pd.DataFrame(rows)


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_returns_200(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.asyncio
class TestSummaryEndpoint:
    async def test_summary_with_mock_data(self, mock_cache_data):
        from app.cache import get_cache
        import pandas as pd
        cache = get_cache()
        cache.store([], [], pd.DataFrame(), pd.DataFrame(), mock_cache_data)

        with patch("app.main.ensure_data_loaded", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/summary")
        assert response.status_code == 200
        data = response.json()
        assert "mae_mw" in data
        assert "rmse_mw" in data
        assert "mean_bias_mw" in data
        assert data["matched_intervals"] == 4


@pytest.mark.asyncio
class TestForecastActualsEndpoint:
    async def test_returns_data(self, mock_cache_data):
        from app.cache import get_cache
        import pandas as pd
        cache = get_cache()
        cache.store([], [], pd.DataFrame(), pd.DataFrame(), mock_cache_data)

        with patch("app.main.ensure_data_loaded", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/forecast-actuals")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["total"] == 4

    async def test_date_filter(self, mock_cache_data):
        from app.cache import get_cache
        import pandas as pd
        cache = get_cache()
        cache.store([], [], pd.DataFrame(), pd.DataFrame(), mock_cache_data)

        with patch("app.main.ensure_data_loaded", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/forecast-actuals?date_from=2026-01-16")
        assert response.status_code == 200
        assert response.json()["total"] == 0  # No data on Jan 16


@pytest.mark.asyncio
class TestDataQualityEndpoint:
    async def test_returns_quality_info(self, mock_cache_data):
        from app.cache import get_cache
        import pandas as pd
        cache = get_cache()
        cache.store([], [], pd.DataFrame(), pd.DataFrame(), mock_cache_data)

        with patch("app.main.ensure_data_loaded", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/data-quality")
        assert response.status_code == 200
        data = response.json()
        assert "matched_intervals" in data
        assert "missing_actuals" in data
