/**
 * ActualVsForecastChart — line chart comparing wind actual vs eligible forecast (MW)
 */
import React from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine,
} from 'recharts';
import { formatMW, formatDateShort } from '../utils/format.js';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', borderRadius: 8, padding: '10px 14px', fontSize: '0.8rem' }}>
      <div style={{ color: 'var(--color-text-muted)', marginBottom: 6 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, marginBottom: 2 }}>
          <span style={{ fontWeight: 600 }}>{p.name}:</span> {formatMW(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function ActualVsForecastChart({ data }) {
  if (!data?.length) return null;

  // Downsample for performance if many points
  const MAX_POINTS = 300;
  const step = data.length > MAX_POINTS ? Math.ceil(data.length / MAX_POINTS) : 1;
  const chartData = data
    .filter((_, i) => i % step === 0)
    .map((d) => ({
      label: `${d.delivery_date} SP${d.period}`,
      actual: d.actual_mw,
      forecast: d.eligible_forecast_mw,
    }))
    .filter((d) => d.actual !== null || d.forecast !== null);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
        <XAxis
          dataKey="label"
          tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
          tickLine={false}
          interval={Math.floor(chartData.length / 6)}
        />
        <YAxis
          tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
          tickFormatter={(v) => `${v} MW`}
          tickLine={false}
          axisLine={false}
          width={72}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}
        />
        <Line
          type="monotone"
          dataKey="actual"
          name="Actual (FUELHH)"
          stroke="var(--chart-actual)"
          strokeWidth={1.5}
          dot={false}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="forecast"
          name="Eligible Forecast (WINDFOR)"
          stroke="var(--chart-forecast)"
          strokeWidth={1.5}
          dot={false}
          connectNulls={false}
          strokeDasharray="4 2"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
