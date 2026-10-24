/**
 * Frontend tests — utility functions and component smoke tests
 */
import { describe, it, expect } from 'vitest';
import { formatMW, formatNumber, formatPct, signedErrorColor, formatDateShort } from '../utils/format.js';

describe('formatMW', () => {
  it('formats positive MW', () => {
    expect(formatMW(1234.5)).toBe('1,235 MW');
  });
  it('returns dash for null', () => {
    expect(formatMW(null)).toBe('—');
  });
  it('formats zero', () => {
    expect(formatMW(0)).toBe('0 MW');
  });
});

describe('formatNumber', () => {
  it('rounds to 1 decimal by default', () => {
    expect(formatNumber(1234.56)).toBe('1,234.6');
  });
  it('returns dash for undefined', () => {
    expect(formatNumber(undefined)).toBe('—');
  });
});

describe('formatPct', () => {
  it('formats percentage', () => {
    expect(formatPct(98.5)).toBe('98.5%');
  });
  it('handles null', () => {
    expect(formatPct(null)).toBe('—');
  });
});

describe('signedErrorColor', () => {
  it('returns amber for large positive (overforecast)', () => {
    expect(signedErrorColor(200)).toBe('var(--color-amber)');
  });
  it('returns teal for large negative (underforecast)', () => {
    expect(signedErrorColor(-200)).toBe('var(--color-teal)');
  });
  it('returns green for near-zero error', () => {
    expect(signedErrorColor(10)).toBe('var(--color-green)');
  });
  it('handles null', () => {
    expect(signedErrorColor(null)).toBe('var(--color-text-muted)');
  });
});

describe('formatDateShort', () => {
  it('formats a date string', () => {
    const result = formatDateShort('2026-01-15');
    expect(result).toMatch(/15/);
    expect(result).toMatch(/Jan/);
  });
  it('handles null', () => {
    expect(formatDateShort(null)).toBe('—');
  });
});
