"""SQLAlchemy ORM models."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, Text, DECIMAL, BigInteger, ForeignKey, Index, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base

class Platform(enum.Enum):
    """Platform enumeration."""
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"

class OpportunityStatus(enum.Enum):
    """Opportunity status enumeration."""
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"

class HealthStatus(enum.Enum):
    """API health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"

class MatchedContract(Base):
    """Matched contract pairs across platforms."""
    __tablename__ = 'matched_contracts'
    
    id = Column(Integer, primary_key=True)
    kalshi_id = Column(String(255), nullable=False)
    polymarket_id = Column(String(255), nullable=False)
    event_title = Column(String(500), nullable=False)
    match_score = Column(Float, nullable=False)
    verified = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    prices = relationship("Price", back_populates="contract", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="contract", cascade="all, delete-orphan")
    bayesian_states = relationship("BayesianState", back_populates="contract", cascade="all, delete-orphan")

class Price(Base):
    """Time-series price observations."""
    __tablename__ = 'prices'

    id = Column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey('matched_contracts.id', ondelete='CASCADE'), nullable=False)
    platform = Column(Enum('kalshi', 'polymarket'), nullable=False)
    probability = Column(DECIMAL(6, 5), nullable=False)
    bid_price = Column(DECIMAL(6, 5))
    ask_price = Column(DECIMAL(6, 5))
    volume_24h = Column(DECIMAL(15, 2))
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (
        # Core query pattern: filter by contract + platform + time window
        Index('ix_prices_contract_platform_ts', 'contract_id', 'platform', 'timestamp'),
        # Probability must be a valid probability value
        CheckConstraint('probability >= 0 AND probability <= 1', name='ck_prices_probability'),
    )

    # Relationships
    contract = relationship("MatchedContract", back_populates="prices")

class Opportunity(Base):
    """Arbitrage opportunities."""
    __tablename__ = 'opportunities'

    id = Column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey('matched_contracts.id', ondelete='CASCADE'), nullable=False)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime)
    raw_spread = Column(DECIMAL(6, 5), nullable=False)
    fee_adjusted_spread = Column(DECIMAL(6, 5), nullable=False)
    kalshi_prob_open = Column(DECIMAL(6, 5), nullable=False)
    polymarket_prob_open = Column(DECIMAL(6, 5), nullable=False)
    kalshi_prob_close = Column(DECIMAL(6, 5))
    polymarket_prob_close = Column(DECIMAL(6, 5))
    peak_spread = Column(DECIMAL(6, 5), nullable=False)
    peak_time = Column(DateTime)
    decay_observations = Column(Integer, default=0)
    status = Column(Enum('open', 'closed', 'expired'), default='open')
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        # Core query pattern: open opportunities per contract
        Index('ix_opportunities_contract_status', 'contract_id', 'status'),
    )

    # Relationships
    contract = relationship("MatchedContract", back_populates="opportunities")

class BayesianState(Base):
    """Bayesian posterior parameters for rolling window."""
    __tablename__ = 'bayesian_state'
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey('matched_contracts.id', ondelete='CASCADE'), nullable=False)
    platform = Column(Enum('kalshi', 'polymarket'), nullable=False)
    alpha = Column(DECIMAL(10, 4), nullable=False)
    beta = Column(DECIMAL(10, 4), nullable=False)
    observations_count = Column(Integer, nullable=False)
    last_updated = Column(DateTime, nullable=False)
    
    # Relationships
    contract = relationship("MatchedContract", back_populates="bayesian_states")

class APIHealth(Base):
    """Platform API status monitoring."""
    __tablename__ = 'api_health'
    
    id = Column(Integer, primary_key=True)
    platform = Column(Enum('kalshi', 'polymarket'), nullable=False, unique=True)
    status = Column(Enum('healthy', 'degraded', 'down'), nullable=False)
    last_successful_call = Column(DateTime)
    last_error = Column(DateTime)
    error_message = Column(Text)
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
