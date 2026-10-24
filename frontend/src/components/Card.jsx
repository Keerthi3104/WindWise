/**
 * Card — surface container with optional title and action slot
 */
import React from 'react';

export default function Card({ title, subtitle, children, action, className = '', style = {} }) {
  return (
    <div
      className={`ww-card ${className}`}
      style={{
        background: 'var(--color-bg-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-6)',
        boxShadow: 'var(--shadow-card)',
        ...style,
      }}
    >
      {(title || action) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: title ? 'var(--space-4)' : 0 }}>
          <div>
            {title && (
              <h3 style={{ fontSize: '0.875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-secondary)', marginBottom: subtitle ? '2px' : 0 }}>
                {title}
              </h3>
            )}
            {subtitle && (
              <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{subtitle}</p>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
