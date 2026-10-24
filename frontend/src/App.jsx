import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import Overview from './pages/Overview.jsx';
import ForecastExplorer from './pages/ForecastExplorer.jsx';
import AccuracyHistory from './pages/AccuracyHistory.jsx';
import DataQuality from './pages/DataQuality.jsx';
import { useApi } from './hooks/useApi.js';
import { api } from './services/api.js';
import './styles/globals.css';

// Global shimmer keyframe (injected once)
const shimmerStyle = `
  @keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
`;

export default function App() {
  const { data: healthData } = useApi(api.health);

  return (
    <BrowserRouter>
      <style>{shimmerStyle}</style>
      <div style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>
        <Sidebar healthData={healthData} />
        <main style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/explorer" element={<ForecastExplorer />} />
            <Route path="/accuracy" element={<AccuracyHistory />} />
            <Route path="/data-quality" element={<DataQuality />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
