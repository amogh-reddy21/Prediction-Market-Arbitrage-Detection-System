"""Bayesian probability smoothing and signal generation."""

import numpy as np
from scipy.stats import beta
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from loguru import logger

from .config import config
from .database import get_db_session
from .models import Price, BayesianState, MatchedContract

class BayesianEngine:
    """Bayesian probability updates using Beta distribution."""
    
    def __init__(self, window_size: int = None):
        """
        Initialize Bayesian engine.
        
        Args:
            window_size: Number of observations in rolling window
        """
        self.window_size = window_size or config.BAYESIAN_WINDOW_SIZE
        
    def update_posterior(
        self, 
        contract_id: int, 
        platform: str, 
        new_probability: float
    ) -> float:
        """
        Update Bayesian posterior with new observation.
        
        Uses conjugate Beta prior for binomial likelihood.
        
        Args:
            contract_id: MatchedContract ID
            platform: 'kalshi' or 'polymarket'
            new_probability: New probability observation (0.0-1.0)
            
        Returns:
            Smoothed posterior mean probability
        """
        with get_db_session() as session:
            # Get or create Bayesian state
            state = session.query(BayesianState).filter_by(
                contract_id=contract_id,
                platform=platform
            ).first()
            
            if not state:
                # Initialize with uninformative prior: Beta(1, 1) = Uniform(0, 1)
                state = BayesianState(
                    contract_id=contract_id,
                    platform=platform,
                    alpha=1.0,
                    beta=1.0,
                    observations_count=0,
                    last_updated=datetime.now(timezone.utc)
                )
                session.add(state)
            
            # Get recent observations from rolling window
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                seconds=config.POLL_INTERVAL_SECONDS * self.window_size
            )
            
            recent_prices = session.query(Price).filter(
                Price.contract_id == contract_id,
                Price.platform == platform,
                Price.timestamp >= cutoff_time
            ).order_by(Price.timestamp.desc()).limit(self.window_size).all()
            
            # Recalculate posterior from scratch using all observations in window
            observations = [float(p.probability) for p in recent_prices] + [new_probability]
            
            # Update using method of moments
            # For Beta distribution: mean = alpha / (alpha + beta)
            # variance = alpha * beta / ((alpha + beta)^2 * (alpha + beta + 1))
            
            obs_array = np.array(observations)
            mean = np.mean(obs_array)
            variance = np.var(obs_array)
            
            # Prevent division by zero
            if variance > 0 and mean > 0 and mean < 1:
                # Method of moments estimation
                alpha = mean * ((mean * (1 - mean) / variance) - 1)
                beta_param = (1 - mean) * ((mean * (1 - mean) / variance) - 1)
                
                # Ensure parameters are valid
                alpha = max(alpha, 0.1)
                beta_param = max(beta_param, 0.1)
            else:
                # Fall back to pseudocount approach
                successes = sum(obs_array)
                failures = len(obs_array) - successes
                alpha = 1.0 + successes
                beta_param = 1.0 + failures
            
            # Update state
            state.alpha = float(alpha)
            state.beta = float(beta_param)
            state.observations_count = len(observations)
            state.last_updated = datetime.now(timezone.utc)
            
            session.commit()
            
            # Posterior mean
            posterior_mean = alpha / (alpha + beta_param)
            
            logger.debug(
                f"Updated posterior for contract {contract_id} ({platform}): "
                f"α={alpha:.2f}, β={beta_param:.2f}, mean={posterior_mean:.4f}"
            )
            
            return posterior_mean
    
    def get_smoothed_probability(
        self, 
        contract_id: int, 
        platform: str
    ) -> Optional[float]:
        """
        Get current smoothed probability from Bayesian state.
        
        Args:
            contract_id: MatchedContract ID
            platform: 'kalshi' or 'polymarket'
            
        Returns:
            Smoothed probability or None if no state exists
        """
        with get_db_session() as session:
            state = session.query(BayesianState).filter_by(
                contract_id=contract_id,
                platform=platform
            ).first()
            
            if not state:
                return None
            
            # Posterior mean
            return float(state.alpha) / (float(state.alpha) + float(state.beta))
    
    def get_posterior_credible_interval(
        self, 
        contract_id: int, 
        platform: str,
        confidence: float = 0.95
    ) -> Optional[Tuple[float, float]]:
        """
        Get Bayesian credible interval for probability.
        
        Args:
            contract_id: MatchedContract ID
            platform: 'kalshi' or 'polymarket'
            confidence: Confidence level (default 95%)
            
        Returns:
            (lower_bound, upper_bound) tuple or None
        """
        with get_db_session() as session:
            state = session.query(BayesianState).filter_by(
                contract_id=contract_id,
                platform=platform
            ).first()
            
            if not state:
                return None
            
            alpha = float(state.alpha)
            beta_param = float(state.beta)
            
            # Compute credible interval
            tail = (1 - confidence) / 2
            lower = beta.ppf(tail, alpha, beta_param)
            upper = beta.ppf(1 - tail, alpha, beta_param)
            
            return (lower, upper)
    
    def compute_spread(
        self,
        contract_id: int,
        kalshi_prob: float,
        polymarket_prob: float,
        use_bayesian: bool = True
    ) -> Dict[str, float]:
        """
        Compute spread between platforms with fee adjustment.
        
        Args:
            contract_id: MatchedContract ID
            kalshi_prob: Raw Kalshi probability
            polymarket_prob: Raw Polymarket probability
            use_bayesian: Whether to use Bayesian smoothing
            
        Returns:
            Dictionary with raw_spread, fee_adjusted_spread, and probabilities
        """
        if use_bayesian:
            # Update and get smoothed probabilities
            kalshi_smoothed = self.update_posterior(contract_id, 'kalshi', kalshi_prob)
            poly_smoothed = self.update_posterior(contract_id, 'polymarket', polymarket_prob)
        else:
            kalshi_smoothed = kalshi_prob
            poly_smoothed = polymarket_prob
        
        # Raw spread (absolute difference)
        raw_spread = abs(poly_smoothed - kalshi_smoothed)
        
        # Fee-adjusted spread
        # To profit, you need spread > (fee_kalshi + fee_polymarket)
        total_fees = config.FEE_KALSHI + config.FEE_POLYMARKET
        fee_adjusted_spread = raw_spread - total_fees

        return {
            'raw_spread': raw_spread,
            'fee_adjusted_spread': fee_adjusted_spread,   # Preserve sign; callers use is_opportunity() to threshold
            'kalshi_prob': kalshi_smoothed,
            'polymarket_prob': poly_smoothed,
            'total_fees': total_fees
        }
    
    def is_opportunity(self, spread_data: Dict[str, float]) -> bool:
        """
        Determine if spread represents a tradeable opportunity.
        
        Args:
            spread_data: Output from compute_spread()
            
        Returns:
            True if opportunity exceeds threshold
        """
        return spread_data['fee_adjusted_spread'] >= config.MIN_SPREAD_THRESHOLD
