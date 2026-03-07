"""Configuration management for the arbitrage system."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env for local development (no-op if the file doesn't exist)
load_dotenv()


class Config:
    """Application configuration.

    All values that come from environment variables are exposed as properties
    so they are read at access time, not at import time.  This is critical for
    Railway (and Render/Heroku) where env vars are injected after the Python
    process starts.
    """

    # ── Static constants (no env var) ────────────────────────────────────────
    KALSHI_BASE_URL      = 'https://api.elections.kalshi.com/trade-api/v2'
    POLYMARKET_BASE_URL  = 'https://clob.polymarket.com'
    POLYMARKET_GAMMA_URL = 'https://gamma-api.polymarket.com'
    LOG_DIR              = Path(__file__).parent.parent / 'logs'

    def __init__(self):
        self.LOG_DIR.mkdir(exist_ok=True)

    # ── Kalshi ────────────────────────────────────────────────────────────────
    @property
    def KALSHI_API_KEY(self):   return os.getenv('KALSHI_API_KEY', '')
    @property
    def KALSHI_EMAIL(self):     return os.getenv('KALSHI_EMAIL', '')
    @property
    def KALSHI_PASSWORD(self):  return os.getenv('KALSHI_PASSWORD', '')

    # ── Polymarket ────────────────────────────────────────────────────────────
    @property
    def POLYMARKET_API_KEY(self): return os.getenv('POLYMARKET_API_KEY', '')

    # ── Database ──────────────────────────────────────────────────────────────
    @property
    def DATABASE_URL(self) -> str:
        # 1. Explicit DATABASE_URL env var takes priority (Railway / Render).
        url = os.getenv('DATABASE_URL')
        if url:
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql+psycopg2://', 1)
            return url

        # 2. MySQL env vars (local dev).
        mysql_host = os.getenv('MYSQL_HOST')
        if mysql_host:
            user     = os.getenv('MYSQL_USER', 'root')
            password = os.getenv('MYSQL_PASSWORD', '')
            host     = mysql_host
            port     = os.getenv('MYSQL_PORT', '3306')
            db       = os.getenv('MYSQL_DATABASE', 'arbitrage_db')
            return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"

        # 3. Generic Postgres fallback (legacy DB_* vars).
        return (
            f"postgresql+psycopg2://"
            f"{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}"
            f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
            f"/{os.getenv('DB_NAME', 'arbitrage_db')}"
        )

    @property
    def SQLALCHEMY_URI(self) -> str:
        return self.DATABASE_URL

    # ── App settings ──────────────────────────────────────────────────────────
    @property
    def POLL_INTERVAL_SECONDS(self): return int(os.getenv('POLL_INTERVAL_SECONDS', 60))
    @property
    def FEE_KALSHI(self):            return float(os.getenv('FEE_KALSHI', 0.07))
    @property
    def FEE_POLYMARKET(self):        return float(os.getenv('FEE_POLYMARKET', 0.02))
    @property
    def MIN_SPREAD_THRESHOLD(self):  return float(os.getenv('MIN_SPREAD_THRESHOLD', 0.015))
    @property
    def FUZZY_MATCH_THRESHOLD(self): return float(os.getenv('FUZZY_MATCH_THRESHOLD', 90.0))
    @property
    def BAYESIAN_WINDOW_SIZE(self):  return int(os.getenv('BAYESIAN_WINDOW_SIZE', 10))
    @property
    def POLYMARKET_ACTIVE_ONLY(self):
        return os.getenv('POLYMARKET_ACTIVE_ONLY', 'True').lower() == 'true'

    # ── Flask ─────────────────────────────────────────────────────────────────
    @property
    def FLASK_HOST(self):  return os.getenv('FLASK_HOST', '0.0.0.0')
    @property
    def FLASK_PORT(self):  return int(os.getenv('FLASK_PORT', 5000))
    @property
    def FLASK_DEBUG(self): return os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # ── Logging ───────────────────────────────────────────────────────────────
    @property
    def LOG_LEVEL(self): return os.getenv('LOG_LEVEL', 'INFO')

    # ── Email notifications ───────────────────────────────────────────────────
    @property
    def EMAIL_NOTIFICATIONS_ENABLED(self):
        return os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'False').lower() == 'true'
    @property
    def SMTP_SERVER(self):   return os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    @property
    def SMTP_PORT(self):     return int(os.getenv('SMTP_PORT', 587))
    @property
    def EMAIL_FROM(self):    return os.getenv('EMAIL_FROM', '')
    @property
    def EMAIL_PASSWORD(self): return os.getenv('EMAIL_PASSWORD', '')
    @property
    def EMAIL_TO(self):      return os.getenv('EMAIL_TO', '')


# Singleton instance
config = Config()
