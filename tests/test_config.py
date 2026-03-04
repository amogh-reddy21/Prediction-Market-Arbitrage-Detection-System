"""Unit tests for configuration management."""

import unittest
import os
from src.config import Config


class TestConfiguration(unittest.TestCase):
    """Test cases for configuration management."""
    
    def test_default_values(self):
        """Test that default configuration values are set."""
        config = Config()
        
        # Test numeric defaults
        self.assertIsInstance(config.POLL_INTERVAL_SECONDS, int)
        self.assertGreater(config.POLL_INTERVAL_SECONDS, 0)
        
        self.assertIsInstance(config.FEE_KALSHI, float)
        self.assertGreaterEqual(config.FEE_KALSHI, 0.0)
        self.assertLessEqual(config.FEE_KALSHI, 1.0)
        
        self.assertIsInstance(config.FEE_POLYMARKET, float)
        self.assertGreaterEqual(config.FEE_POLYMARKET, 0.0)
        self.assertLessEqual(config.FEE_POLYMARKET, 1.0)
        
        self.assertIsInstance(config.MIN_SPREAD_THRESHOLD, float)
        self.assertGreaterEqual(config.MIN_SPREAD_THRESHOLD, 0.0)
        self.assertLessEqual(config.MIN_SPREAD_THRESHOLD, 1.0)
    
    def test_fuzzy_match_threshold(self):
        """Test fuzzy match threshold is valid."""
        config = Config()
        
        self.assertIsInstance(config.FUZZY_MATCH_THRESHOLD, float)
        self.assertGreaterEqual(config.FUZZY_MATCH_THRESHOLD, 0.0)
        self.assertLessEqual(config.FUZZY_MATCH_THRESHOLD, 100.0)
    
    def test_bayesian_window_size(self):
        """Test Bayesian window size is positive integer."""
        config = Config()
        
        self.assertIsInstance(config.BAYESIAN_WINDOW_SIZE, int)
        self.assertGreater(config.BAYESIAN_WINDOW_SIZE, 0)
    
    def test_api_urls(self):
        """Test API URLs are properly formatted."""
        config = Config()
        
        self.assertTrue(config.KALSHI_BASE_URL.startswith('http'))
        self.assertTrue(config.POLYMARKET_BASE_URL.startswith('http'))
        self.assertTrue(config.POLYMARKET_GAMMA_URL.startswith('http'))
    
    def test_database_uri_format(self):
        """Test SQLAlchemy URI has correct format for PostgreSQL."""
        config = Config()
        
        uri = config.SQLALCHEMY_URI
        self.assertTrue(
            uri.startswith('postgresql') or uri.startswith('postgres'),
            f"Expected PostgreSQL URI, got: {uri[:30]}"
        )
        self.assertIn('@', uri)
        self.assertIn('/', uri)
    
    def test_log_directory_creation(self):
        """Test log directory is created."""
        config = Config()
        
        self.assertTrue(config.LOG_DIR.exists())
        self.assertTrue(config.LOG_DIR.is_dir())
    
    def test_fee_total_reasonable(self):
        """Test total fees are reasonable (not > 100%)."""
        config = Config()
        
        total_fees = config.FEE_KALSHI + config.FEE_POLYMARKET
        self.assertLess(total_fees, 1.0)  # Less than 100%
        self.assertGreater(total_fees, 0.0)  # Greater than 0%
    
    def test_threshold_relative_to_fees(self):
        """Test MIN_SPREAD_THRESHOLD is achievable given fees."""
        config = Config()
        
        total_fees = config.FEE_KALSHI + config.FEE_POLYMARKET
        # Threshold should be less than what's possible after fees
        # (i.e., less than 100% - fees)
        self.assertLess(config.MIN_SPREAD_THRESHOLD, 1.0 - total_fees)


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation logic."""
    
    def test_poll_interval_bounds(self):
        """Test polling interval is within reasonable bounds."""
        config = Config()
        
        # Should be at least 10 seconds (not too frequent)
        self.assertGreaterEqual(config.POLL_INTERVAL_SECONDS, 10)
        
        # Should be at most 5 minutes (not too infrequent)
        self.assertLessEqual(config.POLL_INTERVAL_SECONDS, 300)
    
    def test_boolean_configs(self):
        """Test boolean configuration values."""
        config = Config()
        
        self.assertIsInstance(config.POLYMARKET_ACTIVE_ONLY, bool)
        self.assertIsInstance(config.FLASK_DEBUG, bool)
        self.assertIsInstance(config.EMAIL_NOTIFICATIONS_ENABLED, bool)


if __name__ == '__main__':
    unittest.main()
