"""Kalshi API client for fetching prediction markets."""

import httpx
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from pydantic import BaseModel, Field, field_validator


class KalshiMarket(BaseModel):
    """Validated schema for a normalized Kalshi market."""
    platform: str = 'kalshi'
    id: str
    title: str
    yes_bid: float = Field(ge=0.0, le=1.0)
    yes_ask: float = Field(ge=0.0, le=1.0)
    probability: float = Field(ge=0.0, le=1.0)
    volume: float = Field(default=0.0, ge=0.0)
    open_interest: float = Field(default=0.0, ge=0.0)
    close_time: Optional[str] = None

    @field_validator('probability', 'yes_bid', 'yes_ask', mode='before')
    @classmethod
    def clamp_probability(cls, v: float) -> float:
        """Clamp to [0, 1] to handle minor API rounding errors."""
        return max(0.0, min(1.0, float(v)))

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
                
                # Normalize and validate against schema
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
                            
                            try:
                                validated = KalshiMarket(
                                    id=market.get('ticker', ''),
                                    title=market.get('title', ''),
                                    yes_bid=yes_bid / 100.0,
                                    yes_ask=yes_ask / 100.0,
                                    probability=mid_price,
                                    volume=market.get('volume', 0),
                                    open_interest=market.get('open_interest', 0),
                                    close_time=market.get('close_time'),
                                )
                                market_dict = validated.model_dump()
                                market_dict['raw'] = market
                                normalized.append(market_dict)
                            except Exception as e:
                                logger.warning(f"Skipping invalid Kalshi market {market.get('ticker', '?')}: {e}")
                                continue
                
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
