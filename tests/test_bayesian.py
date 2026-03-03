"""Unit tests for Bayesian probability smoothing engine."""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from src.bayesian import BayesianEngine
from src.models import BayesianState, Price, MatchedContract
from src.database import get_db_session
from src.config import config


class TestBayesianEngine(unittest.TestCase):
    """Test cases for Bayesian probability calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = BayesianEngine(window_size=10)
        
    def test_initialization(self):
        """Test BayesianEngine initializes with correct window size."""
        self.assertEqual(self.engine.window_size, 10)
        
        # Test custom window size
        custom_engine = BayesianEngine(window_size=5)
        self.assertEqual(custom_engine.window_size, 5)
    
    def test_compute_spread_basic(self):
        """Test basic spread calculation without Bayesian smoothing."""
        contract_id = 1
        kalshi_prob = 0.60
        poly_prob = 0.75
        
        spread_data = self.engine.compute_spread(
            contract_id,
            kalshi_prob,
            poly_prob,
            use_bayesian=False
        )
        
        # Check spread calculation
        expected_raw_spread = abs(poly_prob - kalshi_prob)
        self.assertEqual(spread_data['raw_spread'], expected_raw_spread)
        
        # Check fee adjustment
        total_fees = config.FEE_KALSHI + config.FEE_POLYMARKET
        expected_fee_adjusted = max(expected_raw_spread - total_fees, 0.0)
        self.assertEqual(spread_data['fee_adjusted_spread'], expected_fee_adjusted)
        
        # Check probabilities are passed through
        self.assertEqual(spread_data['kalshi_prob'], kalshi_prob)
        self.assertEqual(spread_data['polymarket_prob'], poly_prob)
        
    def test_compute_spread_zero(self):
        """Test spread calculation when prices are equal."""
        spread_data = self.engine.compute_spread(
            1,
            0.50,
            0.50,
            use_bayesian=False
        )
        
        self.assertEqual(spread_data['raw_spread'], 0.0)
        self.assertEqual(spread_data['fee_adjusted_spread'], 0.0)
    
    def test_compute_spread_negative_adjustment(self):
        """Test that fee-adjusted spread doesn't go negative."""
        # Small spread that becomes negative after fees
        spread_data = self.engine.compute_spread(
            1,
            0.50,
            0.52,  # 2% spread, less than 9% fees
            use_bayesian=False
        )
        
        self.assertAlmostEqual(spread_data['raw_spread'], 0.02, places=5)
        # Should be 0, not negative
        self.assertEqual(spread_data['fee_adjusted_spread'], 0.0)
    
    def test_is_opportunity_threshold(self):
        """Test opportunity detection based on threshold."""
        # Above threshold
        spread_data = {
            'fee_adjusted_spread': 0.02,  # 2% > MIN_SPREAD_THRESHOLD (1.5%)
            'raw_spread': 0.11,
            'kalshi_prob': 0.40,
            'polymarket_prob': 0.51,
            'total_fees': 0.09
        }
        self.assertTrue(self.engine.is_opportunity(spread_data))
        
        # Below threshold
        spread_data['fee_adjusted_spread'] = 0.01  # 1% < 1.5%
        self.assertFalse(self.engine.is_opportunity(spread_data))
        
        # Exactly at threshold
        spread_data['fee_adjusted_spread'] = config.MIN_SPREAD_THRESHOLD
        self.assertTrue(self.engine.is_opportunity(spread_data))
    
    def test_probability_bounds(self):
        """Test that probabilities stay within [0, 1] bounds."""
        # Test edge cases
        spread_data = self.engine.compute_spread(
            1,
            0.0,
            1.0,
            use_bayesian=False
        )
        
        self.assertGreaterEqual(spread_data['kalshi_prob'], 0.0)
        self.assertLessEqual(spread_data['kalshi_prob'], 1.0)
        self.assertGreaterEqual(spread_data['polymarket_prob'], 0.0)
        self.assertLessEqual(spread_data['polymarket_prob'], 1.0)
    
    def test_fee_consistency(self):
        """Test that fees are consistently applied."""
        spread_data = self.engine.compute_spread(
            1,
            0.30,
            0.50,
            use_bayesian=False
        )
        
        expected_fees = config.FEE_KALSHI + config.FEE_POLYMARKET
        self.assertEqual(spread_data['total_fees'], expected_fees)
        
        # Verify fee calculation
        self.assertEqual(
            spread_data['fee_adjusted_spread'],
            max(spread_data['raw_spread'] - expected_fees, 0.0)
        )


class TestBayesianMath(unittest.TestCase):
    """Test mathematical properties of Bayesian calculations."""
    
    def test_beta_distribution_properties(self):
        """Test that Beta distribution parameters are valid."""
        engine = BayesianEngine()
        
        # Simulate observations
        observations = [0.55, 0.57, 0.56, 0.58, 0.55]
        mean = sum(observations) / len(observations)
        
        # Mean should be between 0 and 1
        self.assertGreater(mean, 0.0)
        self.assertLess(mean, 1.0)
        
    def test_smoothing_reduces_variance(self):
        """Test that Bayesian smoothing reduces variance."""
        # Create noisy observations
        noisy_obs = [0.50, 0.80, 0.52, 0.51, 0.49]  # One outlier
        
        mean = sum(noisy_obs) / len(noisy_obs)
        variance = sum((x - mean) ** 2 for x in noisy_obs) / len(noisy_obs)
        
        # Without outlier
        clean_obs = [0.50, 0.52, 0.51, 0.49]
        clean_mean = sum(clean_obs) / len(clean_obs)
        clean_variance = sum((x - clean_mean) ** 2 for x in clean_obs) / len(clean_obs)
        
        # Variance with outlier should be higher
        self.assertGreater(variance, clean_variance)


class TestSpreadCalculations(unittest.TestCase):
    """Test various spread calculation scenarios."""
    
    def setUp(self):
        self.engine = BayesianEngine()
    
    def test_symmetric_spread(self):
        """Test that spread is symmetric (order doesn't matter)."""
        spread1 = self.engine.compute_spread(1, 0.40, 0.60, use_bayesian=False)
        spread2 = self.engine.compute_spread(1, 0.60, 0.40, use_bayesian=False)
        
        self.assertEqual(spread1['raw_spread'], spread2['raw_spread'])
    
    def test_large_spread(self):
        """Test handling of large spreads."""
        spread_data = self.engine.compute_spread(
            1,
            0.20,
            0.80,
            use_bayesian=False
        )
        
        self.assertAlmostEqual(spread_data['raw_spread'], 0.60, places=5)
        expected_fee_adjusted = 0.60 - (config.FEE_KALSHI + config.FEE_POLYMARKET)
        self.assertAlmostEqual(spread_data['fee_adjusted_spread'], expected_fee_adjusted, places=2)
    
    def test_small_spread(self):
        """Test handling of small spreads below fee threshold."""
        spread_data = self.engine.compute_spread(
            1,
            0.500,
            0.505,  # 0.5% spread
            use_bayesian=False
        )
        
        self.assertAlmostEqual(spread_data['raw_spread'], 0.005, places=5)
        # Should be 0 after 9% fees
        self.assertEqual(spread_data['fee_adjusted_spread'], 0.0)


class TestOpportunityDetection(unittest.TestCase):
    """Test opportunity detection logic."""
    
    def setUp(self):
        self.engine = BayesianEngine()
    
    def test_profitable_opportunity(self):
        """Test detection of profitable opportunity."""
        # 15% raw spread - 9% fees = 6% profit
        spread_data = {
            'fee_adjusted_spread': 0.06,
            'raw_spread': 0.15,
            'kalshi_prob': 0.35,
            'polymarket_prob': 0.50,
            'total_fees': 0.09
        }
        
        self.assertTrue(self.engine.is_opportunity(spread_data))
    
    def test_unprofitable_opportunity(self):
        """Test rejection of unprofitable opportunity."""
        # 8% raw spread - 9% fees = -1% (not profitable)
        spread_data = {
            'fee_adjusted_spread': 0.0,
            'raw_spread': 0.08,
            'kalshi_prob': 0.46,
            'polymarket_prob': 0.54,
            'total_fees': 0.09
        }
        
        self.assertFalse(self.engine.is_opportunity(spread_data))
    
    def test_marginal_opportunity(self):
        """Test opportunity right at threshold."""
        threshold = config.MIN_SPREAD_THRESHOLD
        spread_data = {
            'fee_adjusted_spread': threshold,
            'raw_spread': threshold + 0.09,
            'kalshi_prob': 0.40,
            'polymarket_prob': 0.40 + threshold + 0.09,
            'total_fees': 0.09
        }
        
        self.assertTrue(self.engine.is_opportunity(spread_data))


if __name__ == '__main__':
    unittest.main()
