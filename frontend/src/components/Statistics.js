import React from 'react';

function Statistics({ stats }) {
  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  const formatPercent = (decimal) => {
    return `${(decimal * 100).toFixed(2)}%`;
  };

  return (
    <div className="stats-grid">
      <div className="stat-card">
        <div className="stat-label">Open Opportunities</div>
        <div className="stat-value positive">{stats.open_opportunities}</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Total Detected</div>
        <div className="stat-value">{stats.total_opportunities}</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Closed</div>
        <div className="stat-value">{stats.closed_opportunities}</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Avg Duration</div>
        <div className="stat-value">
          {formatDuration(stats.average_duration_seconds)}
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Edge Half-Life</div>
        <div className="stat-value">
          {formatDuration(stats.edge_half_life_seconds)}
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Avg Peak Spread</div>
        <div className="stat-value positive">
          {formatPercent(stats.average_peak_spread)}
        </div>
      </div>
    </div>
  );
}

export default Statistics;
