# Prediction Market Arbitrage Detection System

Monitors pricing discrepancies on identical events across Kalshi and Polymarket. Uses Bayesian probability smoothing to reduce noise, tracks edge decay over time, and flags exploitable opportunities after fee adjustment.

**Stack:** Python, Flask, SQLAlchemy, PostgreSQL, React, APScheduler, Gunicorn

## How It Works

1. **Data Collection** — Polls Kalshi and Polymarket every 60 seconds via their REST APIs
2. **Contract Matching** — Pairs identical events across platforms using fuzzy string matching (RapidFuzz, 85% threshold)
3. **Signal Engine** — Applies Bayesian Beta-distribution smoothing to raw probabilities, computes fee-adjusted spreads (Kalshi ~7%, Polymarket ~2%)
4. **Opportunity Tracking** — Logs the full lifecycle of each arbitrage opportunity, including spread decay and peak edge
5. **Dashboard** — Flask REST API + React frontend for real-time monitoring of open/closed opportunities

## Backtest Results
- **72,000+** historical observations analyzed
- **151** arbitrage opportunities identified over 30 days
- **4.72%** monthly ROI | **59%** projected annualized | **1.26** Sharpe ratio

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
├── scheduler.py       # Data collection loop (APScheduler)
├── app.py             # Flask REST API
├── kalshi_client.py   # Kalshi API wrapper
├── polymarket_client.py # Polymarket API wrapper
├── matcher.py         # Fuzzy contract matching
├── bayesian.py        # Bayesian probability smoothing
├── tracker.py         # Opportunity lifecycle tracking
├── models.py          # SQLAlchemy ORM models
└── database.py        # DB connection and session management
frontend/
└── src/components/    # React dashboard components
tests/                 # 52 unit tests
```

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | API and platform health status |
| GET | `/api/live` | Currently open opportunities |
| GET | `/api/history` | Closed opportunity history |
| GET | `/api/stats` | Aggregate performance metrics |
