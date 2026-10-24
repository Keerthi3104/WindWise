/**
 * ErrorState — display API or processing errors gracefully
 */
import React from 'react';

export default function ErrorState({ title = 'Unable to load data', message, onRetry }) {
  return (
    <div
      role="alert"
      style={{
        background: 'var(--color-bg-card)',
        border: '1px solid var(--color-red-dim)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-8)',
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>⚠</div>
      <h3 style={{ color: 'var(--color-red)', marginBottom: 'var(--space-2)' }}>{title}</h3>
      {message && (
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem', marginBottom: 'var(--space-4)', maxWidth: 480, margin: '0 auto var(--space-4)' }}>
          {message}
        </p>
      )}
      {onRetry && (
        <button onClick={onRetry} style={btnStyle}>
          Retry
        </button>
      )}
    </div>
  );
}

const btnStyle = {
  background: 'var(--color-bg-elevated)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  padding: '8px 20px',
  cursor: 'pointer',
  fontSize: '0.875rem',
  fontWeight: 600,
};
