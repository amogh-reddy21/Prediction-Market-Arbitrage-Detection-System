import React from 'react';

function History({ opportunities }) {
  const formatPercent = (decimal) => {
    if (decimal === null) return 'N/A';
    return `${(decimal * 100).toFixed(2)}%`;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600) return `${(seconds / 60).toFixed(0)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  return (
    <div className="section">
      <h2>📊 Recent History</h2>

      {opportunities.length === 0 ? (
        <div className="no-data">
          No historical opportunities yet
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Peak Spread</th>
                <th>Duration</th>
                <th>Observations</th>
                <th>Opened</th>
                <th>Closed</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((opp) => (
                <tr key={opp.id}>
                  <td>
                    <div style={{ maxWidth: '300px' }}>
                      {opp.event_title}
                    </div>
                  </td>
                  <td className="spread-positive">
                    <strong>{formatPercent(opp.peak_spread)}</strong>
                  </td>
                  <td>{formatDuration(opp.duration_seconds)}</td>
                  <td>{opp.decay_observations}</td>
                  <td className="timestamp">
                    {formatTime(opp.open_time)}
                  </td>
                  <td className="timestamp">
                    {formatTime(opp.close_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default History;
