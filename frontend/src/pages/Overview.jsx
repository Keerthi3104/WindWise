/**
 * Overview Dashboard — January 2026 aggregate metrics and time-series charts
 */
import React from 'react';
import { useApi } from '../hooks/useApi.js';
import { api } from '../services/api.js';
import MetricCard from '../components/MetricCard.jsx';
import Card from '../components/Card.jsx';
import ActualVsForecastChart from '../components/ActualVsForecastChart.jsx';
import DailyErrorChart from '../components/DailyErrorChart.jsx';
import ErrorState from '../components/ErrorState.jsx';
import Skeleton from '../components/Skeleton.jsx';
import { formatNumber, formatMW } from '../utils/format.js';

function PageHeader() {
  return (
    <div style={{ marginBottom: 'var(--space-8)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
        <div style={{ width: 3, height: 28, background: 'var(--color-lime)', borderRadius: 2 }} />
        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Overview</h1>
      </div>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem', maxWidth: 680 }}>
        Wind generation forecast accuracy for <strong style={{ color: 'var(--color-lime)' }}>January 2026</strong>.
        Forecasts are eligible if published on or before D−1 at 09:20 UTC (EPEX SPOT GB day-ahead gate closure).
        Data: Elexon BMRS FUELHH (WIND actuals) and WINDFOR (forecasts).
      </p>
    </div>
  );
}

function MetricsRow({ data, loading }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
      <MetricCard
        label="Matched Intervals"
        value={loading ? null : formatNumber(data?.matched_intervals, 0)}
        note="Of 1,488 possible (Jan 2026)"
        loading={loading}
        tooltip="Number of 30-minute intervals where both actual and eligible forecast are available"
      />
      <MetricCard
        label="MAE"
        value={loading ? null : formatNumber(data?.mae_mw, 0)}
        unit="MW"
        note="Mean Absolute Error"
        loading={loading}
        tooltip="Mean Absolute Error: average magnitude of forecast error in MW. Lower is better."
      />
      <MetricCard
        label="RMSE"
        value={loading ? null : formatNumber(data?.rmse_mw, 0)}
        unit="MW"
        note="Root Mean Square Error"
        loading={loading}
        tooltip="Root Mean Square Error: penalises large errors more than MAE. In MW."
      />
      <MetricCard
        label="Mean Bias"
        value={loading ? null : (data?.mean_bias_mw !== null ? formatNumber(data.mean_bias_mw, 0) : '—')}
        unit="MW"
        note={data?.mean_bias_mw > 0 ? '▲ Overforecast tendency' : data?.mean_bias_mw < 0 ? '▼ Underforecast tendency' : ''}
        loading={loading}
        tooltip="Mean signed error (forecast − actual). Positive = overforecast on average."
        accent={false}
      />
      <MetricCard
        label="Coverage"
        value={loading ? null : (data?.coverage_pct !== undefined ? `${data.coverage_pct}` : '—')}
        unit="%"
        note="Intervals with both actual & forecast"
        loading={loading}
        accent
        tooltip="Percentage of January 2026 delivery intervals with both actual generation and an eligible forecast."
      />
    </div>
  );
}

function DisclaimerBanner() {
  return (
    <div style={{
      background: 'rgba(34, 211, 238, 0.07)',
      border: '1px solid rgba(34, 211, 238, 0.2)',
      borderRadius: 'var(--radius-md)',
      padding: 'var(--space-4)',
      fontSize: '0.75rem',
      color: 'var(--color-text-secondary)',
      marginBottom: 'var(--space-6)',
    }}>
      <strong style={{ color: 'var(--color-teal)' }}>Dataset scope:</strong>{' '}
      This dashboard analyses <strong>wind generation only</strong> (MW). It does not contain consumer demand,
      electricity prices, thermal plant availability, or total system generation.
      Procurement cost savings cannot be calculated from wind data alone.
      Positive signed error = forecast exceeded actual (overforecast).
      Percentage errors are omitted because actual wind generation can be zero.
    </div>
  );
}

export default function Overview() {
  const { data: summary, loading: sumLoading, error: sumError, reload: reloadSummary } = useApi(api.summary);
  const { data: actuals, loading: actualsLoading, error: actualsError } = useApi(
    () => api.forecastActuals({ limit: 1488 }),
    []
  );

  if (sumError) {
    return (
      <div style={pageWrap}>
        <PageHeader />
        <ErrorState
          title="Could not load summary data"
          message={sumError}
          onRetry={reloadSummary}
        />
      </div>
    );
  }

  return (
    <div style={pageWrap}>
      <PageHeader />
      <DisclaimerBanner />
      <MetricsRow data={summary} loading={sumLoading} />

      {/* Cutoff assumption */}
      {summary?.cutoff_assumption && (
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 'var(--space-6)', padding: '8px 12px', background: 'var(--color-bg-surface)', borderRadius: 'var(--radius-md)', borderLeft: '3px solid var(--color-lime)' }}>
          <strong style={{ color: 'var(--color-lime)' }}>Cutoff assumption:</strong> {summary.cutoff_assumption}.{' '}
          {summary.timezone}
        </div>
      )}

      {/* Time-series chart */}
      <Card title="Actual vs Eligible Forecast — Wind Generation MW" style={{ marginBottom: 'var(--space-6)' }}>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
          Solid line = FUELHH WIND actual · Dashed line = latest eligible WINDFOR forecast before D−1 09:20 UTC cutoff.
          Data may be down-sampled for performance.
        </p>
        {actualsLoading ? (
          <Skeleton height={300} />
        ) : actualsError ? (
          <ErrorState title="Could not load time-series data" message={actualsError} />
        ) : (
          <ActualVsForecastChart data={actuals?.data ?? []} />
        )}
      </Card>

      {/* Daily error chart */}
      <Card title="Daily Forecast Error Summary" subtitle="MAE, RMSE and Mean Bias per delivery day">
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
          Positive bias = overforecast. Negative bias = underforecast. Each point is an average over 48 settlement periods.
        </p>
        {sumLoading ? (
          <Skeleton height={220} />
        ) : (
          <DailyErrorChart data={summary?.daily_summaries ?? []} />
        )}
      </Card>
    </div>
  );
}

const pageWrap = { padding: 'var(--space-8)', flex: 1, maxWidth: 1200, width: '100%' };
