/**
 * Sidebar navigation
 */
import React from 'react';
import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: '◈' },
  { to: '/explorer', label: 'Forecast Explorer', icon: '◉' },
  { to: '/accuracy', label: 'Accuracy History', icon: '◎' },
  { to: '/data-quality', label: 'Data Quality', icon: '◐' },
];

export default function Sidebar({ healthData }) {
  return (
    <aside
      aria-label="Main navigation"
      style={{
        width: 220,
        flexShrink: 0,
        background: 'var(--color-bg-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        position: 'sticky',
        top: 0,
        height: '100vh',
        overflowY: 'auto',
      }}
    >
      {/* Brand */}
      <div style={{ padding: 'var(--space-6)', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
          <div style={{ width: 32, height: 32, background: 'var(--color-lime)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 2L12 7H9L7 5Z" fill="#0a1628"/>
              <ellipse cx="9" cy="11" rx="5" ry="4" stroke="#0a1628" strokeWidth="1.5" fill="none"/>
              <circle cx="9" cy="11" r="1.5" fill="#0a1628"/>
            </svg>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--color-text-primary)', letterSpacing: '-0.02em' }}>WindWise</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--color-lime)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Analytics</div>
          </div>
        </div>

        {/* Period badge */}
        <div style={{ background: 'var(--color-bg-elevated)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', fontSize: '0.7rem' }}>
          <div style={{ color: 'var(--color-text-muted)', marginBottom: 2 }}>Analysis Period</div>
          <div style={{ color: 'var(--color-lime)', fontWeight: 700 }}>January 2026</div>
        </div>
      </div>

      {/* Nav links */}
      <nav style={{ flex: 1, padding: 'var(--space-4) var(--space-3)' }}>
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-3)',
              padding: 'var(--space-3) var(--space-3)',
              borderRadius: 'var(--radius-md)',
              marginBottom: 'var(--space-1)',
              color: isActive ? 'var(--color-lime)' : 'var(--color-text-secondary)',
              background: isActive ? 'rgba(163, 230, 53, 0.1)' : 'transparent',
              fontWeight: isActive ? 700 : 500,
              fontSize: '0.875rem',
              textDecoration: 'none',
              transition: 'all 0.15s',
              borderLeft: isActive ? '2px solid var(--color-lime)' : '2px solid transparent',
            })}
          >
            <span style={{ fontSize: '1rem', opacity: 0.8 }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer info */}
      <div style={{ padding: 'var(--space-4)', borderTop: '1px solid var(--color-border-subtle)', fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>
        <div style={{ marginBottom: 4 }}>
          <span style={{ color: 'var(--color-text-muted)' }}>Cutoff: </span>
          <span style={{ color: 'var(--color-teal)', fontWeight: 600 }}>D−1 09:20 UTC</span>
        </div>
        <div style={{ marginBottom: 4 }}>
          <span style={{ color: 'var(--color-text-muted)' }}>Timezone: </span>
          <span>UTC / GMT</span>
        </div>
        <div>
          <span style={{ color: 'var(--color-text-muted)' }}>Source: </span>
          <a href="https://bmrs.elexon.co.uk" target="_blank" rel="noreferrer" style={{ color: 'var(--color-teal)' }}>Elexon BMRS</a>
        </div>
        {healthData && (
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: healthData.status === 'ok' ? 'var(--color-green)' : 'var(--color-red)' }} />
            <span>{healthData.status === 'ok' ? 'API Online' : 'API Error'}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
