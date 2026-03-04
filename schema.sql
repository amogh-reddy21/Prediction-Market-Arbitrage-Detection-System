-- Prediction Market Arbitrage Database Schema
-- PostgreSQL

-- Matched contract pairs across platforms
CREATE TABLE matched_contracts (
    id          SERIAL PRIMARY KEY,
    kalshi_id   VARCHAR(255) NOT NULL,
    polymarket_id VARCHAR(255) NOT NULL,
    event_title VARCHAR(500) NOT NULL,
    match_score FLOAT NOT NULL,
    verified    BOOLEAN NOT NULL DEFAULT FALSE,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_matched_contracts_pair UNIQUE (kalshi_id, polymarket_id)
);

CREATE INDEX idx_matched_contracts_active   ON matched_contracts (active);
CREATE INDEX idx_matched_contracts_verified ON matched_contracts (verified);

-- Time-series price observations
CREATE TYPE platform_enum AS ENUM ('kalshi', 'polymarket');

CREATE TABLE prices (
    id          BIGSERIAL PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES matched_contracts (id) ON DELETE CASCADE,
    platform    platform_enum NOT NULL,
    probability NUMERIC(6,5) NOT NULL CHECK (probability BETWEEN 0 AND 1),
    bid_price   NUMERIC(6,5),
    ask_price   NUMERIC(6,5),
    volume_24h  NUMERIC(15,2),
    timestamp   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_prices_contract_platform_ts UNIQUE (contract_id, platform, timestamp)
);

CREATE INDEX idx_prices_contract_time  ON prices (contract_id, timestamp);
CREATE INDEX idx_prices_platform_time  ON prices (platform, timestamp);
CREATE INDEX idx_prices_timestamp      ON prices (timestamp);

-- Arbitrage opportunities
CREATE TYPE opportunity_status AS ENUM ('open', 'closed', 'expired');

CREATE TABLE opportunities (
    id                      BIGSERIAL PRIMARY KEY,
    contract_id             INTEGER NOT NULL REFERENCES matched_contracts (id) ON DELETE CASCADE,
    open_time               TIMESTAMPTZ NOT NULL,
    close_time              TIMESTAMPTZ,
    raw_spread              NUMERIC(6,5) NOT NULL,
    fee_adjusted_spread     NUMERIC(6,5) NOT NULL,
    kalshi_prob_open        NUMERIC(6,5) NOT NULL,
    polymarket_prob_open    NUMERIC(6,5) NOT NULL,
    kalshi_prob_close       NUMERIC(6,5),
    polymarket_prob_close   NUMERIC(6,5),
    peak_spread             NUMERIC(6,5) NOT NULL,
    peak_time               TIMESTAMPTZ,
    decay_observations      INTEGER NOT NULL DEFAULT 0,
    status                  opportunity_status NOT NULL DEFAULT 'open',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_opportunities_status           ON opportunities (status);
CREATE INDEX idx_opportunities_open_time        ON opportunities (open_time);
CREATE INDEX idx_opportunities_contract_status  ON opportunities (contract_id, status);

-- Bayesian posterior parameters (rolling window state)
CREATE TABLE bayesian_state (
    id                  SERIAL PRIMARY KEY,
    contract_id         INTEGER NOT NULL REFERENCES matched_contracts (id) ON DELETE CASCADE,
    platform            platform_enum NOT NULL,
    alpha               NUMERIC(10,4) NOT NULL,
    beta                NUMERIC(10,4) NOT NULL,
    observations_count  INTEGER NOT NULL,
    last_updated        TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_bayesian_state_contract_platform UNIQUE (contract_id, platform)
);

CREATE INDEX idx_bayesian_state_last_updated ON bayesian_state (last_updated);

-- Platform API health
CREATE TYPE health_status AS ENUM ('healthy', 'degraded', 'down');

CREATE TABLE api_health (
    id                    SERIAL PRIMARY KEY,
    platform              platform_enum NOT NULL,
    status                health_status NOT NULL,
    last_successful_call  TIMESTAMPTZ,
    last_error            TIMESTAMPTZ,
    error_message         TEXT,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_api_health_platform UNIQUE (platform)
);

INSERT INTO api_health (platform, status) VALUES
    ('kalshi',      'healthy'),
    ('polymarket',  'healthy');
