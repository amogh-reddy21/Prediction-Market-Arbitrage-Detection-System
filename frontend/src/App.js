import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import LiveOpportunities from './components/LiveOpportunities';
import Statistics from './components/Statistics';
import History from './components/History';

function App() {
  const [stats, setStats] = useState(null);
  const [liveOpps, setLiveOpps] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = async () => {
    try {
      const [statsRes, liveRes, historyRes] = await Promise.all([
        axios.get('/api/statistics'),
        axios.get('/api/live'),
        axios.get('/api/history?limit=20')
      ]);

      setStats(statsRes.data);
      setLiveOpps(liveRes.data.opportunities);
      setHistory(historyRes.data.opportunities);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="App">
        <div className="loading">
          <h2>Loading arbitrage data...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <div className="header">
        <h1>🎯 Prediction Market Arbitrage</h1>
        <p>Real-time monitoring across Kalshi and Polymarket</p>
        {lastUpdate && (
          <p className="timestamp">
            Last updated: {lastUpdate.toLocaleTimeString()}
            <span className="pulse"> ●</span>
          </p>
        )}
      </div>

      {error && (
        <div className="error">
          ⚠️ Error: {error}
        </div>
      )}

      {stats && <Statistics stats={stats} />}

      <LiveOpportunities opportunities={liveOpps} />

      <History opportunities={history} />
    </div>
  );
}

export default App;
