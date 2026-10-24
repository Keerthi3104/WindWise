/**
 * Data Quality — API status, record counts, missing values, refresh action
 */
import React, { useState } from 'react';
import { useApi } from '../hooks/useApi.js';
import { api } from '../services/api.js';
import Card from '../components/Card.jsx';
import ErrorState from '../components/ErrorState.jsx';
import Skeleton from '../components/Skeleton.jsx';
import { formatDateTime } from '../utils/format.js';

function QualityRow({ label, value, warn = false, note }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: 'var(--space-3) 0', borderBottom: '1px solid var(--color-border-subtle)',
    }}>
      <div>
        <div style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>{label}</div>
        {note && <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>{note}</div>}
      </div>
      <div style={{
        fontWeight: 700, fontSize: '1.1rem',
        color: warn ? 'var(--color-amber)' : 'var(--color-lime)',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {value ?? '—'}
      </div>
    </div>
  );
}

export default function DataQuality() {
  const { data, loading, error, reload } = useApi(api.dataQuality);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState('');

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshMsg('');
    try {
      const res = await api.refresh();
      setRefreshMsg(res?.message ?? 'Refresh triggered');
      setTimeout(() => reload(), 3000);
    } catch (e) {
      setRefreshMsg(`Error: ${e.message}`);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div style={pageWrap}>
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
          <div style={{ width: 3, height: 28, background: 'var(--color-teal)', borderRadius: 2 }} />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Data Quality</h1>
        </div>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
          Elexon BMRS API fetch status, record counts, coverage gaps, and data quality indicators for January 2026.
        </p>
      </div>

      {error && <ErrorState title="Could not load data quality" message={error} onRetry={reload} />}

      {!error && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-6)' }}>
          {/* API Status */}
          <Card title="API & Cache Status">
            {loading ? <Skeleton height={180} /> : (
              <>
                <QualityRow label="Status" value={data?.status === 'ok' ? '✓ OK' : '✗ Error'} warn={data?.status !== 'ok'} />
                <QualityRow label="Last Successful Fetch" value={formatDateTime(data?.last_fetch_time)} />
                <QualityRow label="Cache TTL" value={data?.cache_ttl_seconds ? `${data.cache_ttl_seconds}s` : '—'} note="Automatic cache expiry" />
                {data?.last_error && (
                  <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', marginTop: 'var(--space-3)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-red)', fontWeight: 700, marginBottom: 4 }}>Last Error</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', wordBreak: 'break-all' }}>{data.last_error}</div>
                  </div>
                )}
                <div style={{ marginTop: 'var(--space-5)' }}>
                  <button onClick={handleRefresh} disabled={refreshing} style={btnStyle}>
                    {refreshing ? 'Refreshing…' : '↻ Refresh from Elexon API'}
                  </button>
                  {refreshMsg && <p style={{ fontSize: '0.75rem', color: 'var(--color-teal)', marginTop: 8 }}>{refreshMsg}</p>}
                </div>
              </>
            )}
          </Card>

          {/* Record counts */}
          <Card title="Record Counts">
            {loading ? <Skeleton height={180} /> : (
              <>
                <QualityRow label="Raw FUELHH WIND Records" value={(data?.raw_actual_records ?? 0).toLocaleString()} note="From Elexon BMRS /datasets/FUELHH/stream" />
                <QualityRow label="Raw WINDFOR Records" value={(data?.raw_forecast_records ?? 0).toLocaleString()} note="From Elexon BMRS /datasets/WINDFOR/stream" />
                <QualityRow label="Merged Intervals" value={(data?.merged_intervals ?? 0).toLocaleString()} note="After outer join on (date, period)" />
                <QualityRow label="Matched Intervals" value={(data?.matched_intervals ?? 0).toLocaleString()} note="Both actual and eligible forecast present" />
              </>
            )}
          </Card>

          {/* Data gaps */}
          <Card title="Coverage Gaps">
            {loading ? <Skeleton height={180} /> : (
              <>
                <QualityRow label="Missing Actuals" value={(data?.missing_actuals ?? 0).toLocaleString()} warn={(data?.missing_actuals ?? 0) > 0} note="Intervals with no FUELHH WIND record" />
                <QualityRow label="Missing Forecasts" value={(data?.missing_forecasts ?? 0).toLocaleString()} warn={(data?.missing_forecasts ?? 0) > 0} note="Intervals with no eligible WINDFOR record" />
                <QualityRow label="Unmatched Intervals" value={(data?.unmatched_intervals ?? 0).toLocaleString()} warn={(data?.unmatched_intervals ?? 0) > 0} note="Missing actual or forecast (not both)" />
                <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--color-bg-elevated)', borderRadius: 'var(--radius-md)', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  Missing values are represented as <strong style={{ color: 'var(--color-text-secondary)' }}>null/—</strong> in the data,
                  never as zero. A missing actual or forecast is explicitly labelled "unavailable".
                </div>
              </>
            )}
          </Card>

          {/* Data sources */}
          <Card title="Data Sources">
            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
              <p style={{ marginBottom: 8 }}>
                <strong style={{ color: 'var(--color-lime)' }}>Actuals:</strong> Elexon BMRS FUELHH stream<br />
                <code style={{ color: 'var(--color-teal)', fontSize: '0.72rem' }}>/datasets/FUELHH/stream?settlementDateFrom=2026-01-01&amp;settlementDateTo=2026-01-31&amp;fuelType=WIND</code>
              </p>
              <p style={{ marginBottom: 8 }}>
                <strong style={{ color: 'var(--color-lime)' }}>Forecasts:</strong> Elexon BMRS WINDFOR stream<br />
                <code style={{ color: 'var(--color-teal)', fontSize: '0.72rem' }}>/datasets/WINDFOR/stream?publishDateTimeFrom=2025-12-30T00:00:00Z&amp;publishDateTimeTo=2026-02-01T12:00:00Z</code>
              </p>
              <p style={{ marginBottom: 8 }}>
                <strong style={{ color: 'var(--color-amber)' }}>Cutoff:</strong> EPEX SPOT GB day-ahead gate closure = D−1 at 09:20 UTC.
                Only forecasts with publishTime ≤ cutoff are eligible for each delivery date.
              </p>
              <p>
                <strong style={{ color: 'var(--color-text-secondary)' }}>Scope:</strong> Wind generation only (MW).
                No demand, prices, thermal availability or total system data.
              </p>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

const pageWrap = { padding: 'var(--space-8)', flex: 1, maxWidth: 1200, width: '100%' };
const btnStyle = {
  padding: '8px 16px', borderRadius: 'var(--radius-md)',
  background: 'var(--color-bg-elevated)', border: '1px solid var(--color-lime)',
  color: 'var(--color-lime)', fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer',
};
