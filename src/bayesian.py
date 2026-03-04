"""Bayesian probability smoothing and signal generation."""

import numpy as np
from scipy.stats import beta
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from loguru import logger

from .config import config
from .database import get_db_session
from .models import BayesianState, MatchedContract

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
        Update Bayesian posterior with a new observation using conjugate Beta-Binomial update.

        Instead of recomputing from the raw price window on every tick (O(window) DB
        reads per call), we store the running (alpha, beta) parameters and apply the
        conjugate update rule directly:

            alpha_new = alpha_old + p          (fractional pseudo-success)
            beta_new  = beta_old  + (1 - p)   (fractional pseudo-failure)

        A rolling-window effect is achieved by decaying old parameters toward the
        uninformative prior once the observation count exceeds the window size.

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
                # Uninformative prior: Beta(1, 1) = Uniform(0, 1)
                state = BayesianState(
                    contract_id=contract_id,
                    platform=platform,
                    alpha=1.0,
                    beta=1.0,
                    observations_count=0,
                    last_updated=datetime.now(timezone.utc)
                )
                session.add(state)

            alpha = float(state.alpha)
            beta_param = float(state.beta)
            n = state.observations_count

            # Rolling-window decay: once we have a full window of observations,
            # shrink the accumulated parameters proportionally so that the effective
            # weight stays bounded at window_size rather than growing without limit.
            if n >= self.window_size:
                scale = (self.window_size - 1) / self.window_size
                alpha = alpha * scale
                beta_param = beta_param * scale

            # Conjugate Beta-Binomial update: treat probability as a fractional count
            alpha += new_probability
            beta_param += (1.0 - new_probability)

            # Guard against numerical edge cases
            alpha = max(alpha, 1e-6)
            beta_param = max(beta_param, 1e-6)

            # Persist updated state
            state.alpha = alpha
            state.beta = beta_param
            state.observations_count = n + 1
            state.last_updated = datetime.now(timezone.utc)

            session.commit()

            posterior_mean = alpha / (alpha + beta_param)

            logger.debug(
                f"Updated posterior for contract {contract_id} ({platform}): "
                f"α={alpha:.4f}, β={beta_param:.4f}, mean={posterior_mean:.4f}"
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
        kalshi_observations = 0
        poly_observations = 0

        if use_bayesian:
            # Update and get smoothed probabilities
            kalshi_smoothed = self.update_posterior(contract_id, 'kalshi', kalshi_prob)
            poly_smoothed = self.update_posterior(contract_id, 'polymarket', polymarket_prob)

            # Get observation counts to compute confidence
            with get_db_session() as session:
                k_state = session.query(BayesianState).filter_by(
                    contract_id=contract_id, platform='kalshi'
                ).first()
                p_state = session.query(BayesianState).filter_by(
                    contract_id=contract_id, platform='polymarket'
                ).first()
                kalshi_observations = k_state.observations_count if k_state else 0
                poly_observations = p_state.observations_count if p_state else 0
        else:
            kalshi_smoothed = kalshi_prob
            poly_smoothed = polymarket_prob

        # Raw spread (absolute difference)
        raw_spread = abs(poly_smoothed - kalshi_smoothed)

        # Fee-adjusted spread
        # To profit, you need spread > (fee_kalshi + fee_polymarket)
        total_fees = config.FEE_KALSHI + config.FEE_POLYMARKET
        fee_adjusted_spread = raw_spread - total_fees

        # Confidence: ramps from 0 → 1 as observations accumulate up to window_size.
        # Requires at least 5 observations on each platform before any confidence > 0.
        min_obs = min(kalshi_observations, poly_observations)
        confidence = min(1.0, max(0.0, (min_obs - 5) / max(self.window_size - 5, 1)))

        return {
            'raw_spread': raw_spread,
            'fee_adjusted_spread': fee_adjusted_spread,
            'kalshi_prob': kalshi_smoothed,
            'polymarket_prob': poly_smoothed,
            'total_fees': total_fees,
            'confidence': confidence,
            'observations': min_obs,
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
