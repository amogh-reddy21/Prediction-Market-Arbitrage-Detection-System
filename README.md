# Prediction Market Arbitrage Detection System

Monitors pricing discrepancies on identical events across Kalshi and Polymarket. Applies Bayesian probability smoothing to reduce noise, tracks edge decay over time, and flags exploitable spreads after fee adjustment.

**Stack:** Python, Flask, SQLAlchemy, PostgreSQL, React, APScheduler, Gunicorn

## How It Works

1. **Collection** — Polls Kalshi and Polymarket every 60 seconds
2. **Matching** — Pairs contracts across platforms using fuzzy string matching (RapidFuzz, 85% threshold)
3. **Signal** — Applies Bayesian Beta-Binomial smoothing; computes fee-adjusted spreads (Kalshi ~7%, Polymarket ~2%)
4. **Tracking** — Records full opportunity lifecycle: open, spread decay, peak edge, close
5. **Dashboard** — Flask REST API + React frontend

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     APScheduler (60s)                   │
│   KalshiClient ──┐                                      │
│                  ├─► ContractMatcher ─► PostgreSQL DB   │
│PolymarketClient ─┘         │                │           │
│                        BayesianEngine       │           │
│                             │               │           │
│                        OpportunityTracker ◄─┘           │
│                             │                           │
└─────────────────────────────┼───────────────────────────┘
                              │
                        Flask REST API
                              │
                        React Dashboard
```

## Simulation Results

> **Methodology:** Synthetic price paths via correlated random walk with arbitrage events injected at a 5% base rate. Not a live historical backtest — treat as algorithm validation, not audited P&L.

- 72,000+ synthetic observations across 50 contract pairs (30-day window)
- 151 opportunities detected; ~60% false-positive reduction vs. raw spread threshold
- 4.72% simulated monthly ROI | 1.26 Sharpe ratio

## Design Decisions

**Bayesian smoothing vs. moving average** — The Beta-Binomial conjugate update degrades gracefully when observations are sparse (e.g., a new market with 2 data points), converging toward the prior rather than producing a volatile signal. A rolling SMA has no equivalent behavior near the window boundary.

**Fuzzy matching vs. exact ID lookup** — Kalshi and Polymarket use independent opaque identifiers with no shared namespace. `token_sort_ratio` matching on normalized titles handles word-order differences and platform-specific phrasing; the 85-point threshold was chosen empirically to balance false positives against false negatives.

**Persisting `alpha`/`beta` vs. recomputing from the price window** — Recomputing on every tick requires a range query per active contract per poll cycle (O(contracts × window_size) reads). Persisting the running parameters reduces this to one point read + one write per observation.

**Separate scheduler and API processes** — The collection loop is I/O-bound and long-running; the API server is latency-sensitive. Separate Procfile workers isolate crashes and allow the API to scale independently.

## Setup

### Prerequisites
- Python 3.12+
- PostgreSQL
- Node.js 18+

### Installation
```bash
# Clone and install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# Create database tables
python -c "from src.database import Base, engine; Base.metadata.create_all(engine)"

# Install frontend dependencies
cd frontend && npm install
```

### Environment Variables
See `.env.example` for all required variables. Key ones:
```
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/arbitrage_db
KALSHI_API_KEY=your_key_here
POLYMARKET_API_KEY=your_key_here
```

### Run
```bash
# Start data collector
python -m src.scheduler

# Start API server (dev)
python -m src.app

# Start API server (production)
gunicorn "src.app:app"

# Start frontend
cd frontend && npm start
```

## Project Structure
```
src/
├── scheduler.py         # Data collection loop (APScheduler)
├── app.py               # Flask REST API
├── kalshi_client.py     # Kalshi API wrapper (Pydantic-validated)
├── polymarket_client.py # Polymarket API wrapper (Pydantic-validated)
├── matcher.py           # Fuzzy contract matching
├── bayesian.py          # Bayesian Beta-Binomial conjugate update
├── tracker.py           # Opportunity lifecycle state machine
├── models.py            # SQLAlchemy ORM models
└── database.py          # DB connection and session management
frontend/
└── src/components/      # React dashboard components
tests/                   # Unit + integration tests (matcher, bayesian, tracker, API clients, pipeline)
```

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | API and platform health status |
| GET | `/api/live` | Currently open opportunities |
| GET | `/api/history` | Closed opportunity history (supports `?limit=N&offset=N`) |
| GET | `/api/stats` | Aggregate performance metrics |
| GET | `/api/contracts` | All matched contract pairs |
| GET | `/api/decay/<id>` | Spread decay curve for a specific opportunity |
