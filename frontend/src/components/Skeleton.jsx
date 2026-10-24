/**
 * Skeleton — loading placeholder
 */
import React from 'react';

export default function Skeleton({ width = '100%', height = 20, borderRadius = 4, style = {} }) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading…"
      style={{
        width,
        height,
        borderRadius,
        background: 'linear-gradient(90deg, var(--color-bg-elevated) 0%, var(--color-bg-surface) 50%, var(--color-bg-elevated) 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        ...style,
      }}
    />
  );
}
