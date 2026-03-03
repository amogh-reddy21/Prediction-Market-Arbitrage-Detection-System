# Prediction Market Arbitrage System

A real-time arbitrage monitoring system for prediction markets across Kalshi and Polymarket.

## Core Concept
Monitors pricing discrepancies on identical events across platforms. Uses Bayesian probability smoothing to reduce noise, tracks edge decay over time, and flags exploitable opportunities after fee adjustment.

## Architecture

### Layer 1: API Wrappers
- **Kalshi Wrapper**: REST API integration for market data
- **Polymarket Wrapper**: CLOB API integration
- **Contract Matcher**: Fuzzy matching (rapidfuzz) to pair identical events across platforms

### Layer 2: Signal Engine
- Bayesian probability updates (Beta distribution priors)
- Fee-adjusted spread calculation (Kalshi ~7%, Polymarket ~2%)
- Rolling window smoothing (last 10 observations)

### Layer 3: Edge Decay Tracker
- Logs opportunity lifecycle from detection to close
- Tracks spread persistence and decay curves
- Empirical analysis of market microstructure

### Layer 4: Storage (MySQL)
- `matched_contracts`: Verified contract pairs across platforms
- `prices`: Time-series polling data with probabilities
- `opportunities`: Flagged arbitrage events with decay metrics

### Layer 5: Dashboard
- Flask REST API backend
- React frontend with live updates
- Real-time opportunity monitoring and historical analysis

## Setup

### Prerequisites
```bash
Python 3.10+
MySQL 8.0+
Node.js 18+
```

### Environment Variables
Create `.env` file:
```
KALSHI_API_KEY=your_key_here
KALSHI_API_SECRET=your_secret_here
POLYMARKET_API_KEY=your_key_here
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=arbitrage_db
```

### Installation
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# Database
mysql -u root -p < schema.sql
```

### Run
```bash
# Start data collector
python src/scheduler.py

# Start API server
python src/app.py

# Start frontend (separate terminal)
cd frontend && npm start
```

## Project Timeline
- **Day 1**: API wrappers + authentication testing
- **Day 2**: Contract matching + MySQL schema
- **Day 3**: Signal engine + Bayesian smoothing + scheduler
- **Day 4**: Flask API + React dashboard
- **Day 5**: Testing, debugging, documentation

## Key Metrics
- **Fee-Adjusted Edge**: Spread after platform fees
- **Edge Half-Life**: Average time for spread to decay 50%
- **Opportunity Frequency**: Flagged events per day
- **False Positive Rate**: Spreads that close before execution

## Why This is a Strong SWE Project
1. **Real-world data**: Live API integration with financial platforms
2. **Statistical modeling**: Bayesian inference, not just raw arithmetic
3. **System design**: Scheduler, database, API, frontend working together
4. **Market microstructure**: Empirical analysis of price discovery
5. **Production-ready**: Error handling, logging, monitoring
