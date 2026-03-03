import React from 'react';

function LiveOpportunities({ opportunities }) {
  const formatPercent = (decimal) => {
    return `${(decimal * 100).toFixed(2)}%`;
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600) return `${(seconds / 60).toFixed(0)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  return (
    <div className="section">
      <h2>
        🔴 Live Opportunities
        <span className="badge live">{opportunities.length}</span>
      </h2>

      {opportunities.length === 0 ? (
        <div className="no-data">
          No active opportunities above threshold
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Spread</th>
                <th>Fee-Adj Spread</th>
                <th>Kalshi</th>
                <th>Polymarket</th>
                <th>Duration</th>
                <th>Peak</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((opp) => (
                <tr key={opp.id}>
                  <td>
                    <div style={{ maxWidth: '300px' }}>
                      {opp.event_title}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '4px' }}>
                      <a 
                        href={`https://kalshi.com/markets/${opp.kalshi_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="platform-link"
                      >
                        Kalshi ↗
                      </a>
                      {' | '}
                      <a 
                        href={`https://polymarket.com/event/${opp.polymarket_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="platform-link"
                      >
                        Poly ↗
                      </a>
                    </div>
                  </td>
                  <td className="spread-positive">
                    {formatPercent(opp.raw_spread)}
                  </td>
                  <td className="spread-positive">
                    <strong>{formatPercent(opp.fee_adjusted_spread)}</strong>
                  </td>
                  <td>{formatPercent(opp.kalshi_prob)}</td>
                  <td>{formatPercent(opp.polymarket_prob)}</td>
                  <td>{formatDuration(opp.duration_seconds)}</td>
                  <td>{formatPercent(opp.peak_spread)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default LiveOpportunities;
