/**
 * Forecast Explorer — interval-level table with date/period selector
 */
import React, { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi.js';
import { api } from '../services/api.js';
import Card from '../components/Card.jsx';
import ErrorState from '../components/ErrorState.jsx';
import EmptyState from '../components/EmptyState.jsx';
import Skeleton from '../components/Skeleton.jsx';
import { formatMW, formatDateTime, formatPeriod, formatDateShort, signedErrorColor } from '../utils/format.js';

const DAYS = Array.from({ length: 31 }, (_, i) => {
  const d = String(i + 1).padStart(2, '0');
  return `2026-01-${d}`;
});

export default function ForecastExplorer() {
  const [dateFrom, setDateFrom] = useState('2026-01-01');
  const [dateTo, setDateTo] = useState('2026-01-07');
  const [period, setPeriod] = useState('');
  const [matchedOnly, setMatchedOnly] = useState(false);
  const [sortKey, setSortKey] = useState('delivery_date');
  const [sortDir, setSortDir] = useState('asc');

  const params = useMemo(() => ({
    date_from: dateFrom,
    date_to: dateTo,
    ...(period ? { period } : {}),
    matched_only: matchedOnly,
    limit: 500,
  }), [dateFrom, dateTo, period, matchedOnly]);

  const { data, loading, error, reload } = useApi(
    () => api.forecastActuals(params),
    [dateFrom, dateTo, period, matchedOnly]
  );

  const rows = data?.data ?? [];

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, sortKey, sortDir]);

  function handleSort(key) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  }

  function SortIcon({ colKey }) {
    if (sortKey !== colKey) return <span style={{ opacity: 0.3, marginLeft: 4 }}>⇅</span>;
    return <span style={{ marginLeft: 4, color: 'var(--color-lime)' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  return (
    <div style={pageWrap}>
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
          <div style={{ width: 3, height: 28, background: 'var(--color-teal)', borderRadius: 2 }} />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Forecast Explorer</h1>
        </div>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
          Inspect interval-level actual generation, eligible forecast, signed error, and forecast publication timestamps.
          Signed error = forecast − actual. Positive = overforecast.
        </p>
      </div>

      {/* Filters */}
      <Card title="Filters" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-4)', alignItems: 'flex-end' }}>
          <label style={labelStyle}>
            <span style={labelText}>From</span>
            <select value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={selectStyle}>
              {DAYS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label style={labelStyle}>
            <span style={labelText}>To</span>
            <select value={dateTo} onChange={e => setDateTo(e.target.value)} style={selectStyle}>
              {DAYS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label style={labelStyle}>
            <span style={labelText}>Settlement Period</span>
            <select value={period} onChange={e => setPeriod(e.target.value)} style={selectStyle}>
              <option value="">All periods</option>
              {Array.from({ length: 48 }, (_, i) => (
                <option key={i + 1} value={i + 1}>SP{i + 1}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
            <input type="checkbox" checked={matchedOnly} onChange={e => setMatchedOnly(e.target.checked)}
              style={{ accentColor: 'var(--color-lime)' }} />
            Matched only
          </label>
          <a href={api.exportCsvUrl()} download="windwise_jan2026.csv"
            style={{ padding: '6px 14px', borderRadius: 'var(--radius-md)', background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)', fontSize: '0.8rem', fontWeight: 600, textDecoration: 'none' }}>
            ↓ CSV Export
          </a>
        </div>
      </Card>

      {/* Table */}
      <Card title={`Intervals${data?.total !== undefined ? ` — ${data.total} records` : ''}`}>
        {error && <ErrorState title="Load failed" message={error} onRetry={reload} />}
        {loading && <Skeleton height={300} />}
        {!loading && !error && sorted.length === 0 && (
          <EmptyState title="No intervals found" message="Adjust the date range or remove filters." />
        )}
        {!loading && !error && sorted.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  {[
                    { key: 'delivery_date', label: 'Date' },
                    { key: 'period', label: 'SP' },
                    { key: 'actual_mw', label: 'Actual MW' },
                    { key: 'eligible_forecast_mw', label: 'Forecast MW' },
                    { key: 'signed_error_mw', label: 'Signed Error' },
                    { key: 'abs_error_mw', label: 'Abs Error' },
                    { key: 'eligible_publish_time', label: 'Forecast Published' },
                    { key: 'matched', label: 'Matched' },
                  ].map(({ key, label }) => (
                    <th key={key} onClick={() => handleSort(key)}
                      style={{ ...thStyle, cursor: 'pointer', userSelect: 'none' }}>
                      {label}<SortIcon colKey={key} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((row, idx) => (
                  <tr key={idx} style={{ background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                    <td style={tdStyle}>{formatDateShort(row.delivery_date)}</td>
                    <td style={tdStyle}>
                      <span style={{ color: 'var(--color-text-muted)' }}>SP</span>
                      <strong>{row.period}</strong>
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--color-teal)', fontVariantNumeric: 'tabular-nums' }}>
                      {row.actual_mw !== null ? `${Number(row.actual_mw).toLocaleString('en-GB')} MW` : <span style={{ color: 'var(--color-text-muted)' }}>—</span>}
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--color-lime)', fontVariantNumeric: 'tabular-nums' }}>
                      {row.eligible_forecast_mw !== null ? `${Number(row.eligible_forecast_mw).toLocaleString('en-GB')} MW` : <span style={{ color: 'var(--color-text-muted)' }}>—</span>}
                    </td>
                    <td style={{ ...tdStyle, color: signedErrorColor(row.signed_error_mw), fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                      {row.signed_error_mw !== null ? `${row.signed_error_mw > 0 ? '+' : ''}${Number(row.signed_error_mw).toFixed(0)} MW` : '—'}
                    </td>
                    <td style={{ ...tdStyle, fontVariantNumeric: 'tabular-nums' }}>
                      {row.abs_error_mw !== null ? `${Number(row.abs_error_mw).toFixed(0)} MW` : '—'}
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--color-text-secondary)', fontSize: '0.72rem' }}>
                      {formatDateTime(row.eligible_publish_time)}
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                        background: row.matched ? 'var(--color-green)' : 'var(--color-text-muted)',
                      }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.total > sorted.length && (
              <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 12, textAlign: 'center' }}>
                Showing {sorted.length} of {data.total} records. Narrow the date range to see more.
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

const pageWrap = { padding: 'var(--space-8)', flex: 1, maxWidth: 1200, width: '100%' };
const labelStyle = { display: 'flex', flexDirection: 'column', gap: 4 };
const labelText = { fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' };
const selectStyle = {
  padding: '6px 10px', borderRadius: 'var(--radius-md)',
  background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)',
  color: 'var(--color-text-primary)', fontSize: '0.875rem', cursor: 'pointer',
};
const thStyle = {
  padding: '10px 12px', textAlign: 'left', color: 'var(--color-text-muted)',
  fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em',
  borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap',
};
const tdStyle = {
  padding: '8px 12px', borderBottom: '1px solid var(--color-border-subtle)',
  whiteSpace: 'nowrap', color: 'var(--color-text-primary)',
};
