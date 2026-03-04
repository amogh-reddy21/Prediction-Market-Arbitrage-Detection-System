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

## Setup & Deployment

### Option A — Docker Compose (recommended, runs everything locally)

```bash
cp .env.example .env          # fill in secrets
docker compose up --build     # postgres + api + worker + frontend
```

- Frontend → http://localhost
- API      → http://localhost:5000/api/health

### Option B — Render (free tier, one-click)

1. Push the repo to GitHub.
2. In the Render dashboard → **New → Blueprint** → connect the repo.  
   Render reads `render.yaml` and provisions the DB, API web service, and background worker automatically.
3. Set the secret env vars (`KALSHI_API_KEY`, `KALSHI_EMAIL`, `KALSHI_PASSWORD`) in the Render dashboard.

### Option C — Railway

```bash
npm install -g @railway/cli
railway login
railway up            # deploys via railway.json / Dockerfile
```
Add a PostgreSQL plugin in the Railway dashboard and set `DATABASE_URL`.

### Option D — Manual / local dev

**Prerequisites:** Python 3.12+, PostgreSQL, Node.js 18+

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env           # fill in DATABASE_URL and API keys

python -m src.scheduler        # data-collection worker
gunicorn "src.app:app" --config gunicorn.conf.py  # production API

# Frontend (dev server with proxy to Flask)
cd frontend && npm install && npm start

# Frontend (production build served by Flask)
cd frontend && npm run build   # output → frontend/build/
# Flask automatically serves frontend/build/ when it exists
```

### Environment Variables
See `.env.example` for all required variables. Key ones:
```
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/arbitrage_db
KALSHI_API_KEY=your_key_here
KALSHI_EMAIL=your_email_here
KALSHI_PASSWORD=your_password_here
POLYMARKET_API_KEY=your_key_here   # optional
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
