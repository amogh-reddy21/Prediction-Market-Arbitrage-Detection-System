"""Kalshi API client for fetching prediction markets."""

import httpx
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

class KalshiClient:
    """Client for interacting with Kalshi's public API."""
    
    def __init__(self, base_url: str):
        """
        Initialize Kalshi client.
        
        Args:
            base_url: Base URL for Kalshi API (public, no auth needed)
        """
        self.base_url = base_url
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_markets(self, limit: int = 200) -> List[Dict]:
        """
        Fetch markets from Kalshi (public endpoint, no auth required).
        
        Args:
            limit: Maximum number of markets to fetch
            
        Returns:
            List of normalized market dictionaries
        """
        try:
            url = f"{self.base_url}/markets"
            params = {
                'limit': limit
            }
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                markets = data.get('markets', [])
                
                logger.info(f"✓ Fetched {len(markets)} Kalshi markets")
                
                # Normalize to standard format
                normalized = []
                for market in markets:
                    # Only include binary markets with meaningful bid/ask
                    if market.get('market_type') == 'binary':
                        yes_bid = market.get('yes_bid', 0)
                        yes_ask = market.get('yes_ask', 0)
                        
                        # Calculate probability from mid-price (bid+ask)/2
                        # Kalshi prices are in cents (0-100)
                        if yes_bid > 0 or yes_ask > 0:
                            mid_price = (yes_bid + yes_ask) / 2 / 100.0
                            
                            normalized.append({
                                'platform': 'kalshi',
                                'id': market.get('ticker'),
                                'title': market.get('title', ''),
                                'yes_bid': yes_bid / 100.0,
                                'yes_ask': yes_ask / 100.0,
                                'probability': mid_price,
                                'volume': market.get('volume', 0),
                                'open_interest': market.get('open_interest', 0),
                                'close_time': market.get('close_time'),
                                'raw': market
                            })
                
                logger.info(f"✓ Normalized {len(normalized)} Kalshi binary markets")
                return normalized
                
        except Exception as e:
            logger.error(f"✗ Failed to fetch Kalshi markets: {e}")
            raise
    
    def get_market_details(self, ticker: str) -> Dict:
        """
        Get detailed information about a specific market.
        
        Args:
            ticker: Market ticker symbol
            
        Returns:
            Market details dictionary
        """
        try:
            url = f"{self.base_url}/markets/{ticker}"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                return data.get('market', {})
                
        except Exception as e:
            logger.error(f"✗ Failed to fetch market {ticker}: {e}")
            raise
    
    def health_check(self) -> bool:
        """
        Check if Kalshi API is accessible.
        
        Returns:
            True if API is responding, False otherwise
        """
        try:
            url = f"{self.base_url}/markets"
            params = {'limit': 1}
            
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                logger.info("✓ Kalshi API health check passed")
                return True
                
        except Exception as e:
            logger.error(f"✗ Kalshi API health check failed: {e}")
            return False
