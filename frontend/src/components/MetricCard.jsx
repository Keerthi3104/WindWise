/**
 * MetricCard — displays a single KPI with label, value, unit and optional trend
 */
import React from 'react';
import Skeleton from './Skeleton.jsx';

export default function MetricCard({ label, value, unit, note, accent = false, loading = false, tooltip }) {
  return (
    <div
      style={{
        background: 'var(--color-bg-card)',
        border: `1px solid ${accent ? 'var(--color-lime-dim)' : 'var(--color-border)'}`,
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-5) var(--space-6)',
        boxShadow: 'var(--shadow-card)',
        position: 'relative',
      }}
      title={tooltip}
    >
      <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)' }}>
        {label}
      </div>
      {loading ? (
        <Skeleton height={36} width="70%" />
      ) : (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: '2rem', fontWeight: 700, color: accent ? 'var(--color-lime)' : 'var(--color-text-primary)', lineHeight: 1 }}>
            {value ?? '—'}
          </span>
          {unit && (
            <span style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', fontWeight: 500 }}>
              {unit}
            </span>
          )}
        </div>
      )}
      {note && (
        <div style={{ marginTop: 'var(--space-2)', fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
          {note}
        </div>
      )}
    </div>
  );
}
