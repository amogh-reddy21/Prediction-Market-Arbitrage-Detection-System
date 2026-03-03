"""Configuration management for the arbitrage system."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""
    
    # Kalshi API
    KALSHI_API_KEY = os.getenv('KALSHI_API_KEY', '')
    KALSHI_EMAIL = os.getenv('KALSHI_EMAIL', '')
    KALSHI_PASSWORD = os.getenv('KALSHI_PASSWORD', '')
    KALSHI_BASE_URL = 'https://api.elections.kalshi.com/trade-api/v2'
    
    # Polymarket API
    POLYMARKET_API_KEY = os.getenv('POLYMARKET_API_KEY', '')
    POLYMARKET_BASE_URL = 'https://clob.polymarket.com'
    POLYMARKET_GAMMA_URL = 'https://gamma-api.polymarket.com'
    
    # PostgreSQL Database
    # On cloud platforms (Heroku, Railway, Render), set DATABASE_URL directly.
    # Locally, set individual vars or DATABASE_URL=postgresql://user:pass@localhost:5432/arbitrage_db
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        f"postgresql+psycopg2://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'arbitrage_db')}"
    )

    @property
    def MYSQL_URI(self):
        """SQLAlchemy connection string (kept for backward compat — points to Postgres now)."""
        url = self.DATABASE_URL
        # Heroku/Railway sometimes provide postgres:// instead of postgresql://
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql+psycopg2://', 1)
        return url
    
    # Application Settings
    POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', 60))
    FEE_KALSHI = float(os.getenv('FEE_KALSHI', 0.07))
    FEE_POLYMARKET = float(os.getenv('FEE_POLYMARKET', 0.02))
    MIN_SPREAD_THRESHOLD = float(os.getenv('MIN_SPREAD_THRESHOLD', 0.015))  # Lowered from 0.05 to 0.015 (1.5%) for more practical opportunities
    FUZZY_MATCH_THRESHOLD = float(os.getenv('FUZZY_MATCH_THRESHOLD', 85.0))
    BAYESIAN_WINDOW_SIZE = int(os.getenv('BAYESIAN_WINDOW_SIZE', 10))
    POLYMARKET_ACTIVE_ONLY = os.getenv('POLYMARKET_ACTIVE_ONLY', 'True').lower() == 'true'
    
    # Flask API
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Email Notifications
    EMAIL_NOTIFICATIONS_ENABLED = os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'False').lower() == 'true'
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    EMAIL_FROM = os.getenv('EMAIL_FROM', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    EMAIL_TO = os.getenv('EMAIL_TO', '')
    LOG_DIR = Path(__file__).parent.parent / 'logs'
    
    def __init__(self):
        """Ensure log directory exists."""
        self.LOG_DIR.mkdir(exist_ok=True)

# Singleton instance
config = Config()
