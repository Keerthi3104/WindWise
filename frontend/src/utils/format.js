/**
 * Formatting utilities for WindWise
 */

export function formatMW(value, decimals = 0) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return `${Number(value).toLocaleString('en-GB', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })} MW`;
}

export function formatNumber(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return Number(value).toLocaleString('en-GB', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatDateShort(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
  } catch {
    return dateStr;
  }
}

export function formatDateTime(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short',
    });
  } catch {
    return isoStr;
  }
}

export function formatPeriod(period) {
  if (!period) return '—';
  const hour = Math.floor((period - 1) / 2);
  const min = (period - 1) % 2 === 0 ? '00' : '30';
  return `SP${period} (${String(hour).padStart(2, '0')}:${min} UTC)`;
}

export function signedErrorColor(value) {
  if (value === null || value === undefined) return 'var(--color-text-muted)';
  if (value > 50) return 'var(--color-amber)';   // overforecast
  if (value < -50) return 'var(--color-teal)';   // underforecast
  return 'var(--color-green)';                   // close
}

export function formatPct(value) {
  if (value === null || value === undefined) return '—';
  return `${Number(value).toFixed(1)}%`;
}
