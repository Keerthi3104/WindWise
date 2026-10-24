/**
 * EmptyState — shown when no data matches filters
 */
import React from 'react';

export default function EmptyState({ icon = '📭', title = 'No data', message }) {
  return (
    <div style={{ textAlign: 'center', padding: 'var(--space-12) var(--space-8)', color: 'var(--color-text-muted)' }}>
      <div style={{ fontSize: '2.5rem', marginBottom: 'var(--space-3)' }}>{icon}</div>
      <h4 style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)' }}>{title}</h4>
      {message && <p style={{ fontSize: '0.875rem' }}>{message}</p>}
    </div>
  );
}
