-- Prediction Market Arbitrage Database Schema

DROP DATABASE IF EXISTS arbitrage_db;
CREATE DATABASE arbitrage_db;
USE arbitrage_db;

-- Matched contract pairs across platforms
CREATE TABLE matched_contracts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kalshi_id VARCHAR(255) NOT NULL,
    polymarket_id VARCHAR(255) NOT NULL,
    event_title VARCHAR(500) NOT NULL,
    match_score FLOAT NOT NULL,  -- Fuzzy match similarity (0-100)
    verified BOOLEAN DEFAULT FALSE,  -- Manual verification flag
    active BOOLEAN DEFAULT TRUE,  -- Whether we're still monitoring this pair
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_pair (kalshi_id, polymarket_id),
    INDEX idx_active (active),
    INDEX idx_verified (verified)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Time-series price observations
CREATE TABLE prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    contract_id INT NOT NULL,
    platform ENUM('kalshi', 'polymarket') NOT NULL,
    probability DECIMAL(6,5) NOT NULL,  -- 0.00000 to 1.00000
    bid_price DECIMAL(6,5),
    ask_price DECIMAL(6,5),
    volume_24h DECIMAL(15,2),  -- 24-hour trading volume in USD
    timestamp TIMESTAMP(3) NOT NULL,  -- Millisecond precision
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contract_id) REFERENCES matched_contracts(id) ON DELETE CASCADE,
    INDEX idx_contract_time (contract_id, timestamp),
    INDEX idx_platform_time (platform, timestamp),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Arbitrage opportunities
CREATE TABLE opportunities (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    contract_id INT NOT NULL,
    open_time TIMESTAMP(3) NOT NULL,
    close_time TIMESTAMP(3),
    raw_spread DECIMAL(6,5) NOT NULL,  -- Raw probability difference
    fee_adjusted_spread DECIMAL(6,5) NOT NULL,  -- After platform fees
    kalshi_prob_open DECIMAL(6,5) NOT NULL,
    polymarket_prob_open DECIMAL(6,5) NOT NULL,
    kalshi_prob_close DECIMAL(6,5),
    polymarket_prob_close DECIMAL(6,5),
    peak_spread DECIMAL(6,5) NOT NULL,
    peak_time TIMESTAMP(3),
    decay_observations INT DEFAULT 0,  -- Number of price updates while open
    status ENUM('open', 'closed', 'expired') DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (contract_id) REFERENCES matched_contracts(id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_open_time (open_time),
    INDEX idx_contract_status (contract_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Bayesian posterior parameters (rolling window state)
CREATE TABLE bayesian_state (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contract_id INT NOT NULL,
    platform ENUM('kalshi', 'polymarket') NOT NULL,
    alpha DECIMAL(10,4) NOT NULL,  -- Beta distribution alpha parameter
    beta DECIMAL(10,4) NOT NULL,   -- Beta distribution beta parameter
    observations_count INT NOT NULL,  -- Number of observations in rolling window
    last_updated TIMESTAMP(3) NOT NULL,
    UNIQUE KEY unique_contract_platform (contract_id, platform),
    FOREIGN KEY (contract_id) REFERENCES matched_contracts(id) ON DELETE CASCADE,
    INDEX idx_last_updated (last_updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Platform API status and monitoring
CREATE TABLE api_health (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform ENUM('kalshi', 'polymarket') NOT NULL,
    status ENUM('healthy', 'degraded', 'down') NOT NULL,
    last_successful_call TIMESTAMP(3),
    last_error TIMESTAMP(3),
    error_message TEXT,
    consecutive_failures INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_platform (platform)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Initialize API health monitoring
INSERT INTO api_health (platform, status) VALUES 
    ('kalshi', 'healthy'),
    ('polymarket', 'healthy');
