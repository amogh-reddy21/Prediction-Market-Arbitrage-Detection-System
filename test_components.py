"""Test script to verify components work independently."""

import sys
from loguru import logger

# Configure simple logging
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_database():
    """Test database connection."""
    logger.info("Testing database connection...")
    try:
        from src.database import test_connection
        result = test_connection()
        if result:
            logger.success("✓ Database connection works")
            return True
        else:
            logger.error("✗ Database connection failed")
            return False
    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        return False

def test_kalshi():
    """Test Kalshi API."""
    logger.info("Testing Kalshi API...")
    try:
        from src.kalshi_client import KalshiClient
        from src.config import config
        client = KalshiClient(base_url=config.KALSHI_BASE_URL)
        markets = client.get_markets(limit=5)
        
        if markets:
            logger.success(f"✓ Kalshi API works - fetched {len(markets)} markets")
            logger.info(f"Sample: {markets[0]['title'][:60]}...")
            return True
        else:
            logger.warning("⚠ Kalshi API returned no markets")
            return False
    except Exception as e:
        logger.error(f"✗ Kalshi test failed: {e}")
        return False

def test_polymarket():
    """Test Polymarket API."""
    logger.info("Testing Polymarket API...")
    try:
        from src.polymarket_client import PolymarketClient
        client = PolymarketClient()
        markets = client.get_markets(limit=5)
        
        if markets:
            logger.success(f"✓ Polymarket API works - fetched {len(markets)} markets")
            logger.info(f"Sample: {markets[0]['event_slug'][:60]}...")
            return True
        else:
            logger.warning("⚠ Polymarket API returned no markets")
            return False
    except Exception as e:
        logger.error(f"✗ Polymarket test failed: {e}")
        return False

def test_matcher():
    """Test contract matching."""
    logger.info("Testing contract matcher...")
    try:
        from src.matcher import ContractMatcher
        from src.kalshi_client import KalshiClient
        from src.polymarket_client import PolymarketClient
        from src.config import config
        
        kalshi = KalshiClient(base_url=config.KALSHI_BASE_URL)
        poly = PolymarketClient()
        matcher = ContractMatcher()
        
        k_markets = kalshi.get_markets(limit=10)
        p_markets = poly.get_markets(limit=10)
        
        matches = matcher.find_matches(k_markets, p_markets)
        
        if matches:
            logger.success(f"✓ Matcher works - found {len(matches)} matches")
            logger.info(f"Top match (score {matches[0][2]:.1f}): {matches[0][0]['title'][:60]}...")
            return True
        else:
            logger.warning("⚠ No matches found (markets may not overlap)")
            return True  # Not necessarily a failure
    except Exception as e:
        logger.error(f"✗ Matcher test failed: {e}")
        return False

def test_bayesian():
    """Test Bayesian engine."""
    logger.info("Testing Bayesian engine...")
    try:
        from src.bayesian import BayesianEngine
        
        engine = BayesianEngine()
        
        # Test spread calculation
        spread_data = engine.compute_spread(
            contract_id=1,
            kalshi_prob=0.42,
            polymarket_prob=0.47,
            use_bayesian=False  # Skip DB for this test
        )
        
        logger.success("✓ Bayesian engine works")
        logger.info(f"Sample spread: raw={spread_data['raw_spread']:.4f}, fee-adj={spread_data['fee_adjusted_spread']:.4f}")
        return True
    except Exception as e:
        logger.error(f"✗ Bayesian test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("COMPONENT TEST SUITE")
    logger.info("=" * 60)
    
    results = {
        'Database': test_database(),
        'Kalshi API': test_kalshi(),
        'Polymarket API': test_polymarket(),
        'Contract Matcher': test_matcher(),
        'Bayesian Engine': test_bayesian()
    }
    
    logger.info("=" * 60)
    logger.info("TEST RESULTS")
    logger.info("=" * 60)
    
    for component, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{component}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.success("\n🎉 All tests passed! System is ready.")
    else:
        logger.error("\n⚠️  Some tests failed. Check configuration and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main()
