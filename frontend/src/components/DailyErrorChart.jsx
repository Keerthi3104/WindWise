/**
 * DailyErrorChart — bar chart of daily MAE/RMSE/mean bias
 */
import React, { useState } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, LineChart, Line,
} from 'recharts';
import { formatMW, formatDateShort } from '../utils/format.js';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', borderRadius: 8, padding: '10px 14px', fontSize: '0.8rem' }}>
      <div style={{ color: 'var(--color-text-muted)', marginBottom: 6 }}>{formatDateShort(label)}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, marginBottom: 2 }}>
          <span style={{ fontWeight: 600 }}>{p.name}:</span> {p.value !== null ? `${Number(p.value).toFixed(0)} MW` : '—'}
        </div>
      ))}
    </div>
  );
}

export default function DailyErrorChart({ data }) {
  const [view, setView] = useState('mae'); // mae | bias | rmse

  if (!data?.length) return null;

  const chartData = data.map((d) => ({
    date: d.date,
    mae: d.mae_mw,
    rmse: d.rmse_mw,
    bias: d.mean_bias_mw,
  }));

  return (
    <div>
      {/* View toggle */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {[
          { key: 'mae', label: 'MAE' },
          { key: 'rmse', label: 'RMSE' },
          { key: 'bias', label: 'Mean Bias' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setView(key)}
            style={{
              padding: '4px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              background: view === key ? 'var(--color-lime)' : 'var(--color-bg-elevated)',
              color: view === key ? '#0a1628' : 'var(--color-text-secondary)',
              fontWeight: 600,
              fontSize: '0.75rem',
              cursor: 'pointer',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={220}>
        {view === 'bias' ? (
          <BarChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis dataKey="date" tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} tickLine={false} tickFormatter={formatDateShort} />
            <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v} MW`} width={72} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="var(--color-border)" />
            <Bar dataKey="bias" name="Mean Bias" fill="var(--color-amber)" radius={[3, 3, 0, 0]}
              label={false}
              // Colour by positive/negative
              isAnimationActive={false}
              shape={(props) => {
                const { x, y, width, height, value } = props;
                const fill = value >= 0 ? 'var(--color-amber)' : 'var(--color-teal)';
                const rectY = value >= 0 ? y : y + height;
                const rectH = Math.abs(height);
                return <rect x={x} y={rectY} width={width} height={rectH} fill={fill} rx={2} />;
              }}
            />
          </BarChart>
        ) : (
          <LineChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis dataKey="date" tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} tickLine={false} tickFormatter={formatDateShort} />
            <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v} MW`} width={72} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey={view} name={view === 'mae' ? 'MAE' : 'RMSE'}
              stroke={view === 'mae' ? 'var(--color-lime)' : 'var(--color-amber)'}
              strokeWidth={2} dot={{ r: 3, fill: 'var(--color-bg-card)' }} connectNulls={false} />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
