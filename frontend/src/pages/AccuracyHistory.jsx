/**
 * Accuracy History — daily metrics + forecast publication history for a selected interval
 */
import React, { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi.js';
import { api } from '../services/api.js';
import Card from '../components/Card.jsx';
import ErrorState from '../components/ErrorState.jsx';
import EmptyState from '../components/EmptyState.jsx';
import Skeleton from '../components/Skeleton.jsx';
import { formatMW, formatDateTime, formatNumber, formatDateShort } from '../utils/format.js';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts';

const DAYS = Array.from({ length: 31 }, (_, i) => {
  const d = String(i + 1).padStart(2, '0');
  return `2026-01-${d}`;
});

export default function AccuracyHistory() {
  const [selectedDate, setSelectedDate] = useState('2026-01-15');
  const [selectedPeriod, setSelectedPeriod] = useState(18);

  const { data: summary, loading: sumLoading, error: sumError } = useApi(api.summary);
  const { data: history, loading: histLoading, error: histError, reload: reloadHist } = useApi(
    () => api.forecastHistory(selectedDate, selectedPeriod),
    [selectedDate, selectedPeriod]
  );

  const dailyData = useMemo(() => {
    if (!summary?.daily_summaries) return [];
    return summary.daily_summaries.map((d) => ({
      date: d.date,
      mae: d.mae_mw,
      rmse: d.rmse_mw,
      bias: d.mean_bias_mw,
    }));
  }, [summary]);

  return (
    <div style={pageWrap}>
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
          <div style={{ width: 3, height: 28, background: 'var(--color-amber)', borderRadius: 2 }} />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Accuracy History</h1>
        </div>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
          Daily forecast accuracy trends and the full publication history for any selected delivery interval.
          Each forecast vintage is marked eligible or too-late relative to the D−1 09:20 UTC cutoff.
        </p>
      </div>

      {/* Daily metrics chart */}
      <Card title="Daily MAE — January 2026" style={{ marginBottom: 'var(--space-6)' }}>
        {sumLoading && <Skeleton height={200} />}
        {sumError && <ErrorState title="Could not load daily data" message={sumError} />}
        {!sumLoading && !sumError && (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={dailyData} margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="date" tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                tickLine={false} tickFormatter={formatDateShort} />
              <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} tickLine={false}
                axisLine={false} tickFormatter={(v) => `${v} MW`} width={72} />
              <Tooltip
                contentStyle={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', borderRadius: 8, fontSize: '0.8rem' }}
                labelStyle={{ color: 'var(--color-text-muted)' }}
              />
              <Line type="monotone" dataKey="mae" name="MAE (MW)" stroke="var(--color-lime)" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
              <Line type="monotone" dataKey="rmse" name="RMSE (MW)" stroke="var(--color-amber)" strokeWidth={1.5} dot={false} strokeDasharray="4 2" connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Daily summary table */}
      <Card title="Daily Summary Table" style={{ marginBottom: 'var(--space-6)' }}>
        {sumLoading && <Skeleton height={200} />}
        {!sumLoading && !sumError && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  {['Date', 'Matched SP', 'Avg Actual MW', 'Avg Forecast MW', 'MAE MW', 'RMSE MW', 'Bias MW'].map(h => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(summary?.daily_summaries ?? []).map((row, i) => (
                  <tr key={row.date}
                    style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)', cursor: 'pointer' }}
                    onClick={() => setSelectedDate(row.date)}
                  >
                    <td style={{ ...tdStyle, color: 'var(--color-lime)', fontWeight: 600 }}>{row.date}</td>
                    <td style={tdStyle}>{row.matched_intervals ?? '—'}</td>
                    <td style={{ ...tdStyle, color: 'var(--color-teal)' }}>{row.avg_actual_mw !== null ? `${Number(row.avg_actual_mw).toFixed(0)}` : '—'}</td>
                    <td style={{ ...tdStyle, color: 'var(--color-lime)' }}>{row.avg_forecast_mw !== null ? `${Number(row.avg_forecast_mw).toFixed(0)}` : '—'}</td>
                    <td style={tdStyle}>{row.mae_mw !== null ? `${Number(row.mae_mw).toFixed(0)}` : '—'}</td>
                    <td style={tdStyle}>{row.rmse_mw !== null ? `${Number(row.rmse_mw).toFixed(0)}` : '—'}</td>
                    <td style={{ ...tdStyle, color: row.mean_bias_mw > 0 ? 'var(--color-amber)' : 'var(--color-teal)', fontWeight: 600 }}>
                      {row.mean_bias_mw !== null ? `${row.mean_bias_mw > 0 ? '+' : ''}${Number(row.mean_bias_mw).toFixed(0)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: 8 }}>
          Click a row to load its forecast publication history below.
        </p>
      </Card>

      {/* Interval selector */}
      <Card title="Forecast Publication History" subtitle="All WINDFOR vintages for the selected delivery interval">
        <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-5)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={labelStyle}>
            <span style={labelText}>Delivery Date</span>
            <select value={selectedDate} onChange={e => setSelectedDate(e.target.value)} style={selectStyle}>
              {DAYS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label style={labelStyle}>
            <span style={labelText}>Settlement Period</span>
            <select value={selectedPeriod} onChange={e => setSelectedPeriod(Number(e.target.value))} style={selectStyle}>
              {Array.from({ length: 48 }, (_, i) => (
                <option key={i + 1} value={i + 1}>SP{i + 1}</option>
              ))}
            </select>
          </label>
        </div>

        {histLoading && <Skeleton height={200} />}
        {histError && <ErrorState title="Could not load history" message={histError} onRetry={reloadHist} />}

        {!histLoading && !histError && history && (
          <>
            {/* Summary row */}
            <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-5)', flexWrap: 'wrap' }}>
              <InfoChip label="Actual MW" value={history.actual_mw !== null ? `${history.actual_mw} MW` : 'Not available'} color="var(--color-teal)" />
              <InfoChip label="Total Vintages" value={history.total_vintages} />
              <InfoChip label="Eligible Vintages" value={history.eligible_count} color="var(--color-green)" />
              <InfoChip label="Cutoff" value={`D−1 09:20 UTC`} color="var(--color-amber)" />
            </div>

            {history.forecast_vintages.length === 0 ? (
              <EmptyState title="No forecast data" message="No WINDFOR records found for this interval." />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>Published (UTC)</th>
                      <th style={thStyle}>Forecast MW</th>
                      <th style={thStyle}>Eligible?</th>
                      <th style={thStyle}>Cutoff Time</th>
                      <th style={thStyle}>Error vs Actual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.forecast_vintages.map((v, i) => {
                      const err = history.actual_mw !== null && v.forecast_mw !== null
                        ? (v.forecast_mw - history.actual_mw).toFixed(0) : null;
                      return (
                        <tr key={i} style={{
                          background: v.eligible ? 'rgba(163,230,53,0.05)' : 'rgba(239,68,68,0.04)',
                        }}>
                          <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                            {formatDateTime(v.publish_time)}
                          </td>
                          <td style={{ ...tdStyle, color: v.eligible ? 'var(--color-lime)' : 'var(--color-text-muted)', fontWeight: v.eligible ? 700 : 400 }}>
                            {v.forecast_mw !== null ? `${v.forecast_mw} MW` : '—'}
                          </td>
                          <td style={tdStyle}>
                            {v.eligible
                              ? <span style={{ color: 'var(--color-green)', fontWeight: 700 }}>✓ Eligible</span>
                              : <span style={{ color: 'var(--color-red)', fontSize: '0.75rem' }}>✗ Too late</span>}
                          </td>
                          <td style={{ ...tdStyle, color: 'var(--color-text-muted)', fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>
                            {formatDateTime(v.cutoff_time)}
                          </td>
                          <td style={{ ...tdStyle, color: err !== null ? (err > 0 ? 'var(--color-amber)' : 'var(--color-teal)') : 'var(--color-text-muted)' }}>
                            {err !== null ? `${err > 0 ? '+' : ''}${err} MW` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

function InfoChip({ label, value, color = 'var(--color-text-secondary)' }) {
  return (
    <div style={{ background: 'var(--color-bg-elevated)', borderRadius: 'var(--radius-md)', padding: '8px 14px' }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 700, color, fontSize: '0.9rem' }}>{value}</div>
    </div>
  );
}

const pageWrap = { padding: 'var(--space-8)', flex: 1, maxWidth: 1200, width: '100%' };
const labelStyle = { display: 'flex', flexDirection: 'column', gap: 4 };
const labelText = { fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' };
const selectStyle = { padding: '6px 10px', borderRadius: 'var(--radius-md)', background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)', fontSize: '0.875rem', cursor: 'pointer' };
const thStyle = { padding: '10px 12px', textAlign: 'left', color: 'var(--color-text-muted)', fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap' };
const tdStyle = { padding: '8px 12px', borderBottom: '1px solid var(--color-border-subtle)', whiteSpace: 'nowrap' };
