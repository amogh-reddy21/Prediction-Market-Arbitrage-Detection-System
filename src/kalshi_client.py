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
        Fetch political/economic binary markets from Kalshi via the /events endpoint.

        Kalshi's /markets endpoint only returns sports-parlay markets (KXMVE*),
        which have zero overlap with Polymarket.  Real political and economic
        binary markets live under /events with nested market objects.  We
        paginate through all open events, collect every nested binary market
        that has a live bid or ask, normalise to the KalshiMarket schema and
        return the list.

        Args:
            limit: Events to fetch per page (max 200 per Kalshi docs).

        Returns:
            List of normalised market dictionaries.
        """
        try:
            events_url = f"{self.base_url}/events"
            all_raw_markets: List[Dict] = []

            cursor: Optional[str] = None
            pages_fetched = 0
            max_pages = 20  # safety ceiling — 200 events/page × 20 = 4 000 events

            with httpx.Client(timeout=30.0) as client:
                while pages_fetched < max_pages:
                    params: Dict = {
                        'limit': limit,
                        'status': 'open',
                        'with_nested_markets': 'true',
                    }
                    if cursor:
                        params['cursor'] = cursor

                    response = client.get(events_url, headers=self.headers, params=params)
                    response.raise_for_status()
                    data = response.json()

                    events = data.get('events', [])
                    if not events:
                        break

                    for event in events:
                        for market in event.get('markets', []):
                            all_raw_markets.append(market)

                    pages_fetched += 1
                    cursor = data.get('cursor')
                    if not cursor:
                        break

            logger.info(f"✓ Fetched {len(all_raw_markets)} Kalshi markets from {pages_fetched} event page(s)")

            # Normalise and validate
            normalized: List[Dict] = []
            for market in all_raw_markets:
                # Skip sports-parlay series entirely
                ticker: str = market.get('ticker', '')
                if 'KXMVE' in ticker:
                    continue

                if market.get('market_type') != 'binary':
                    continue

                yes_bid = market.get('yes_bid', 0)
                yes_ask = market.get('yes_ask', 0)

                if yes_bid <= 0 and yes_ask <= 0:
                    continue

                # Kalshi prices are in cents (0–100); convert to probability
                mid_price = (yes_bid + yes_ask) / 2 / 100.0

                try:
                    validated = KalshiMarket(
                        id=ticker,
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
                    logger.warning(f"Skipping invalid Kalshi market {ticker}: {e}")
                    continue

            logger.info(f"✓ Normalised {len(normalized)} Kalshi binary political/economic markets")
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
