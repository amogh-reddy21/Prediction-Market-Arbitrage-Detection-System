"""Polymarket API wrapper for CLOB and Gamma endpoints."""

import httpx
from typing import List, Dict, Optional
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import config

class PolymarketClient:
    """Wrapper for Polymarket CLOB and Gamma APIs."""
    
    def __init__(self):
        self.clob_url = config.POLYMARKET_BASE_URL
        self.gamma_url = config.POLYMARKET_GAMMA_URL
        self.api_key = config.POLYMARKET_API_KEY
        
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers (optional key for higher rate limits)."""
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_markets(self, limit: int = 200, active: bool = True) -> List[Dict]:
        """
        Fetch active markets from Polymarket.
        
        Args:
            limit: Maximum number of markets to fetch
            active: Only fetch active markets (if False, includes recent closed markets)
            
        Returns:
            List of normalized market dictionaries
        """
        try:
            # Use Gamma API for simplified market data
            url = f"{self.gamma_url}/markets"
            params = {
                'limit': limit,
                'closed': 'false' if active else None  # Server-side filter for open markets
            }
            
            # Remove None values from params
            params = {k: v for k, v in params.items() if v is not None}
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                
                markets = response.json()
                
                # Normalize to common schema
                normalized = []
                for market in markets:
                    # Skip if explicitly closed (backup filter)
                    if market.get('closed'):
                        continue
                    
                    # Parse outcomes (can be array or JSON string)
                    import json as json_lib
                    outcomes_raw = market.get('outcomes', '[]')
                    if isinstance(outcomes_raw, str):
                        try:
                            outcomes = json_lib.loads(outcomes_raw)
                        except:
                            continue
                    else:
                        outcomes = outcomes_raw
                    
                    # Only process binary yes/no markets
                    if not outcomes or len(outcomes) != 2:
                        continue
                    
                    # Use simplified pricing from outcomePrices instead of orderbook
                    prices_raw = market.get('outcomePrices', '[0, 0]')
                    if isinstance(prices_raw, str):
                        try:
                            prices = json_lib.loads(prices_raw)
                        except:
                            prices = [0, 0]
                    else:
                        prices = prices_raw
                    
                    # prices[0] = Yes, prices[1] = No
                    yes_price = float(prices[0]) if len(prices) > 0 else 0.0
                    no_price = float(prices[1]) if len(prices) > 1 else 0.0
                    
                    # Skip if no pricing data
                    if yes_price == 0 and no_price == 0:
                        continue
                    
                    # Calculate probability (use best available data)
                    probability = yes_price if yes_price > 0 else (1.0 - no_price)
                    
                    normalized.append({
                        'platform': 'polymarket',
                        'id': market.get('conditionId', ''),  # Use 'id' for consistency with Kalshi
                        'market_id': market.get('conditionId', ''),  # Keep for backward compat
                        'question': market.get('question', ''),
                        'title': market.get('question', ''),  # For matcher compatibility
                        'category': market.get('category', 'unknown'),
                        'yes_bid': yes_price * 0.99,  # Approximate bid/ask spread
                        'yes_ask': yes_price * 1.01,
                        'probability': probability,
                        'volume_24h': market.get('volume24hr', 0),
                        'close_time': market.get('endDate'),
                        'timestamp': datetime.now(timezone.utc)
                    })
                
                logger.info(f"✓ Fetched {len(normalized)} Polymarket markets")
                return normalized
                
        except Exception as e:
            logger.error(f"✗ Failed to fetch Polymarket markets: {e}")
            raise
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    def _get_orderbook(self, condition_id: str) -> Optional[Dict]:
        """
        Get orderbook data for a specific market.
        
        Args:
            condition_id: Polymarket condition ID
            
        Returns:
            Dictionary with bid, ask, and probability
        """
        try:
            url = f"{self.clob_url}/book"
            params = {'token_id': condition_id}
            
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                
                book = response.json()
                
                # Extract best bid and ask
                bids = book.get('bids', [])
                asks = book.get('asks', [])
                
                yes_bid = float(bids[0]['price']) if bids else 0.0
                yes_ask = float(asks[0]['price']) if asks else 1.0
                probability = (yes_bid + yes_ask) / 2.0
                
                return {
                    'yes_bid': yes_bid,
                    'yes_ask': yes_ask,
                    'probability': probability
                }
                
        except Exception as e:
            logger.warning(f"Failed to fetch orderbook for {condition_id}: {e}")
            return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_market_detail(self, condition_id: str) -> Optional[Dict]:
        """
        Get detailed information for a specific market.
        
        Args:
            condition_id: Polymarket condition ID
            
        Returns:
            Normalized market dictionary
        """
        try:
            url = f"{self.gamma_url}/markets/{condition_id}"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=self._get_headers())
                response.raise_for_status()
                
                market = response.json()
                orderbook = self._get_orderbook(condition_id)
                
                if not orderbook:
                    return None
                
                return {
                    'platform': 'polymarket',
                    'market_id': condition_id,
                    'event_slug': market['question'],
                    'yes_bid': orderbook['yes_bid'],
                    'yes_ask': orderbook['yes_ask'],
                    'probability': orderbook['probability'],
                    'volume_24h': market.get('volume_24h', 0),
                    'timestamp': datetime.now(timezone.utc)
                }
                
        except Exception as e:
            logger.error(f"✗ Failed to fetch Polymarket market {condition_id}: {e}")
            return None
    
    def get_price(self, condition_id: str) -> Optional[float]:
        """
        Get current probability for a market (simple helper).
        
        Args:
            condition_id: Polymarket condition ID
            
        Returns:
            Probability float (0.0 to 1.0)
        """
        market = self.get_market_detail(condition_id)
        return market['probability'] if market else None
