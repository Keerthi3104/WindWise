/**
 * WindWise API service
 * All requests go to the backend. VITE_API_URL is set in .env.
 * Falls back to same-origin proxy in development (vite.config.js proxies /api).
 */

const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`
  : '';

async function fetchJSON(path, params = {}) {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, String(v));
    }
  });

  const response = await fetch(url.toString());
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error');
    let detail = text;
    try {
      detail = JSON.parse(text)?.detail || text;
    } catch (_) {}
    throw new Error(`API ${response.status}: ${detail}`);
  }
  return response.json();
}

export const api = {
  health: () => fetchJSON('/api/health'),

  summary: () => fetchJSON('/api/summary'),

  forecastActuals: (params = {}) => fetchJSON('/api/forecast-actuals', params),

  forecastHistory: (deliveryDate, period) =>
    fetchJSON('/api/forecast-history', { delivery_date: deliveryDate, period }),

  dataQuality: () => fetchJSON('/api/data-quality'),

  refresh: () =>
    fetch(`${BASE_URL}/api/refresh`, { method: 'POST' }).then((r) => r.json()),

  exportCsvUrl: () => `${BASE_URL}/api/export/csv`,
};
