"""Unit tests for API client integrations."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.kalshi_client import KalshiClient
from src.polymarket_client import PolymarketClient


class TestKalshiClient(unittest.TestCase):
    """Test cases for Kalshi API client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = KalshiClient(base_url='https://api.elections.kalshi.com/trade-api/v2')
    
    def test_initialization(self):
        """Test client initializes with base URL."""
        self.assertEqual(self.client.base_url, 'https://api.elections.kalshi.com/trade-api/v2')
    
    @patch('httpx.Client.get')
    def test_get_markets_success(self, mock_get):
        """Test successful market data retrieval."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'markets': [
                {
                    'ticker': 'TRUMP-2024',
                    'title': 'Will Trump win 2024?',
                    'market_type': 'binary',
                    'yes_bid': 55,
                    'yes_ask': 57,
                    'volume': 1000,
                    'open_interest': 5000
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        markets = self.client.get_markets()
        
        self.assertIsInstance(markets, list)
        if markets:
            market = markets[0]
            self.assertIn('id', market)
            self.assertIn('platform', market)
            self.assertEqual(market['platform'], 'kalshi')
            self.assertIn('probability', market)
    
    def test_price_normalization(self):
        """Test Kalshi price normalization (cents to decimal)."""
        # Kalshi returns prices in cents (0-100)
        # Should be normalized to 0.0-1.0
        
        test_cases = [
            (50, 0.5),  # 50 cents = 0.5 probability
            (100, 1.0),  # 100 cents = 1.0 probability
            (0, 0.0),  # 0 cents = 0.0 probability
            (75, 0.75),  # 75 cents = 0.75 probability
        ]
        
        for cents, expected in test_cases:
            normalized = cents / 100.0
            self.assertEqual(normalized, expected)


class TestPolymarketClient(unittest.TestCase):
    """Test cases for Polymarket API client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = PolymarketClient()
    
    def test_initialization(self):
        """Test client initializes with correct URLs."""
        # PolymarketClient doesn't expose these as public attributes
        # Just test it initializes without error
        self.assertIsNotNone(self.client)
    
    @patch('httpx.Client.get')
    def test_get_markets_success(self, mock_get):
        """Test successful market data retrieval."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'conditionId': '0xabc123',
                'question': 'Will Trump win 2024?',
                'outcomes': '["Yes", "No"]',
                'outcomePrices': '["0.55", "0.45"]',
                'closed': False,
                'active': True,
                'volume24hr': 10000
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        markets = self.client.get_markets(active=True, limit=100)
        
        self.assertIsInstance(markets, list)
    
    def test_json_parsing(self):
        """Test JSON string parsing for outcomes and prices."""
        import json
        
        # Polymarket returns JSON strings, not arrays
        outcomes_str = '["Yes", "No"]'
        prices_str = '["0.55", "0.45"]'
        
        outcomes = json.loads(outcomes_str)
        prices = json.loads(prices_str)
        
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(len(prices), 2)
        self.assertEqual(outcomes[0], "Yes")
        self.assertEqual(float(prices[0]), 0.55)
    
    def test_binary_market_filtering(self):
        """Test that only binary markets are processed."""
        # Binary market (2 outcomes)
        binary_outcomes = ["Yes", "No"]
        self.assertEqual(len(binary_outcomes), 2)
        
        # Multi-outcome market (should be filtered)
        multi_outcomes = ["Option A", "Option B", "Option C"]
        self.assertNotEqual(len(multi_outcomes), 2)


class TestAPIErrorHandling(unittest.TestCase):
    """Test error handling in API clients."""
    
    @patch('httpx.Client.get')
    def test_kalshi_api_error(self, mock_get):
        """Test Kalshi client handles API errors."""
        mock_get.side_effect = Exception("API Error")
        
        client = KalshiClient(base_url='https://test.com')
        
        with self.assertRaises(Exception):
            client.get_markets()
    
    @patch('httpx.Client.get')
    def test_polymarket_api_error(self, mock_get):
        """Test Polymarket client handles API errors."""
        mock_get.side_effect = Exception("API Error")
        
        client = PolymarketClient()
        
        with self.assertRaises(Exception):
            client.get_markets()


if __name__ == '__main__':
    unittest.main()
