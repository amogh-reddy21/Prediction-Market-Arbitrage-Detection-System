"""Main scheduler for data collection and opportunity detection."""

import sys
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from .config import config
from .database import test_connection, get_db_session
from .models import Price, APIHealth
from .kalshi_client import KalshiClient
from .polymarket_client import PolymarketClient
from .matcher import ContractMatcher
from .bayesian import BayesianEngine
from .tracker import OpportunityTracker
from .notifier import EmailNotifier

# Module-level references; populated by main() so that importing this module
# does not trigger API connections or database access at import time.
kalshi: KalshiClient = None       # type: ignore[assignment]
polymarket: PolymarketClient = None  # type: ignore[assignment]
matcher: ContractMatcher = None    # type: ignore[assignment]
bayesian: BayesianEngine = None    # type: ignore[assignment]
tracker: OpportunityTracker = None # type: ignore[assignment]
notifier: EmailNotifier = None     # type: ignore[assignment]

def update_api_health(platform: str, success: bool, error_msg: str = None):
    """Update API health status in database."""
    with get_db_session() as session:
        health = session.query(APIHealth).filter_by(platform=platform).first()
        
        if not health:
            health = APIHealth(platform=platform, status='healthy')
            session.add(health)
        
        now = datetime.now(timezone.utc)
        
        if success:
            health.last_successful_call = now
            health.consecutive_failures = 0
            health.status = 'healthy'
        else:
            health.last_error = now
            health.error_message = error_msg
            health.consecutive_failures += 1
            
            if health.consecutive_failures >= 3:
                health.status = 'down'
            elif health.consecutive_failures >= 1:
                health.status = 'degraded'
        
        session.commit()

def collect_prices():
    """Main data collection job - runs every poll interval."""
    logger.info("=" * 60)
    logger.info(f"Starting price collection cycle at {datetime.now(timezone.utc)}")
    
    # Fetch markets from both platforms
    try:
        kalshi_markets = kalshi.get_markets()
        update_api_health('kalshi', True)
    except Exception as e:
        logger.error(f"Failed to fetch Kalshi markets: {e}")
        update_api_health('kalshi', False, str(e))
        kalshi_markets = []
    
    try:
        polymarket_markets = polymarket.get_markets(active=config.POLYMARKET_ACTIVE_ONLY)
        update_api_health('polymarket', True)
    except Exception as e:
        logger.error(f"Failed to fetch Polymarket markets: {e}")
        update_api_health('polymarket', False, str(e))
        polymarket_markets = []
    
    if not kalshi_markets or not polymarket_markets:
        logger.warning("Insufficient market data, skipping cycle")
        return
    
    # Find and save new matches
    matches = matcher.find_matches(kalshi_markets, polymarket_markets)
    if matches:
        matcher.save_matches(matches)
    
    # Get active matched contracts
    active_contracts = matcher.get_active_matches()
    logger.info(f"Monitoring {len(active_contracts)} active contract pairs")
    
    # Build lookup dicts
    kalshi_dict = {m['id']: m for m in kalshi_markets}
    poly_dict = {m['id']: m for m in polymarket_markets}
    
    # Store prices and compute spreads
    current_spreads = {}
    
    with get_db_session() as session:
        for contract in active_contracts:
            kalshi_market = kalshi_dict.get(contract.kalshi_id)
            poly_market = poly_dict.get(contract.polymarket_id)
            
            if not kalshi_market or not poly_market:
                continue
            
            now = datetime.now(timezone.utc)
            
            # Store prices
            kalshi_price = Price(
                contract_id=contract.id,
                platform='kalshi',
                probability=kalshi_market['probability'],
                bid_price=kalshi_market.get('yes_bid'),
                ask_price=kalshi_market.get('yes_ask'),
                volume_24h=kalshi_market.get('volume_24h'),
                timestamp=now
            )
            
            poly_price = Price(
                contract_id=contract.id,
                platform='polymarket',
                probability=poly_market['probability'],
                bid_price=poly_market.get('yes_bid'),
                ask_price=poly_market.get('yes_ask'),
                volume_24h=poly_market.get('volume_24h'),
                timestamp=now
            )
            
            session.add(kalshi_price)
            session.add(poly_price)
            
            # Compute spread
            spread_data = bayesian.compute_spread(
                contract.id,
                kalshi_market['probability'],
                poly_market['probability'],
                use_bayesian=True
            )
            
            current_spreads[contract.id] = spread_data
            
            # Check if this is a new opportunity
            if bayesian.is_opportunity(spread_data):
                tracker.flag_opportunity(contract.id, spread_data)
                
                # Send email notification for new opportunities
                try:
                    opportunity_data = {
                        'event_description': f"{kalshi_market.get('title', 'Unknown')} vs {poly_market.get('question', 'Unknown')}",
                        'spread_percent': spread_data['raw_spread'] * 100,
                        'expected_roi': spread_data['fee_adjusted_spread'] * 100,
                        'confidence': spread_data.get('confidence', 0) * 100,
                        'kalshi_probability': kalshi_market['probability'] * 100,
                        'kalshi_bid': kalshi_market.get('yes_bid', 0),
                        'kalshi_ask': kalshi_market.get('yes_ask', 0),
                        'polymarket_probability': poly_market['probability'] * 100,
                        'polymarket_bid': poly_market.get('yes_bid', 0),
                        'polymarket_ask': poly_market.get('yes_ask', 0),
                        'recommended_action': f"Buy on {'Kalshi' if kalshi_market['probability'] < poly_market['probability'] else 'Polymarket'}, sell on {'Polymarket' if kalshi_market['probability'] < poly_market['probability'] else 'Kalshi'}",
                        'timestamp': datetime.now(timezone.utc)
                    }
                    notifier.send_arbitrage_alert(opportunity_data)
                except Exception as e:
                    logger.warning(f"Failed to send email notification: {e}")
        
        session.commit()
    
    # Update existing open opportunities
    tracker.update_open_opportunities(current_spreads)
    
    # Expire stale opportunities
    tracker.expire_stale_opportunities()
    
    # Log summary statistics
    stats = tracker.get_statistics()
    logger.info(
        f"📊 Stats: {stats['open_opportunities']} open, "
        f"{stats['closed_opportunities']} closed, "
        f"avg duration: {stats['average_duration_seconds']:.0f}s"
    )
    
    logger.info("Price collection cycle complete")

def initial_match():
    """Run initial contract matching on startup."""
    logger.info("Running initial contract matching...")
    
    try:
        kalshi_markets = kalshi.get_markets(limit=500)
        polymarket_markets = polymarket.get_markets(limit=500, active=config.POLYMARKET_ACTIVE_ONLY)
        
        matches = matcher.find_matches(kalshi_markets, polymarket_markets)
        
        if matches:
            logger.info(f"Found {len(matches)} initial matches")
            matcher.save_matches(matches, verified=False)
            
            # Display top matches for manual verification
            logger.info("\nTop 10 matches for verification:")
            for i, (k, p, score) in enumerate(matches[:10], 1):
                logger.info(f"{i}. [{score:.1f}] {k['event_slug'][:60]}...")
        else:
            logger.warning("No matches found during initial run")
    
    except Exception as e:
        logger.error(f"Initial matching failed: {e}")

def main():
    """Main entry point."""
    global kalshi, polymarket, matcher, bayesian, tracker, notifier

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=config.LOG_LEVEL
    )
    logger.add(
        config.LOG_DIR / "arbitrage_{time}.log",
        rotation="1 day",
        retention="7 days",
        level=config.LOG_LEVEL
    )

    logger.info("🚀 Starting Prediction Market Arbitrage System")

    # Verify DATABASE_URL is actually set (not the localhost fallback)
    db_url = config.DATABASE_URL
    if 'localhost' in db_url or '127.0.0.1' in db_url:
        logger.critical(
            "DATABASE_URL points to localhost — this will fail on Railway. "
            "Go to the Railway dashboard → this service → Variables → "
            "add a reference to your PostgreSQL DATABASE_URL."
        )

    # Initialize all components here — not at module import time
    kalshi = KalshiClient(base_url=config.KALSHI_BASE_URL)
    polymarket = PolymarketClient()
    matcher = ContractMatcher()
    bayesian = BayesianEngine()
    tracker = OpportunityTracker()
    notifier = EmailNotifier()

    # Test database connection — retry for up to 60s to allow Railway's
    # PostgreSQL container time to become ready before we give up.
    import time
    for attempt in range(1, 7):
        if test_connection():
            break
        logger.warning(f"DB not ready (attempt {attempt}/6) — retrying in 10s...")
        time.sleep(10)
    else:
        logger.critical(
            "Could not connect to the database after 60s. "
            "Make sure DATABASE_URL is set in Railway Variables."
        )
        sys.exit(1)

    # Run initial matching
    initial_match()

    # Setup scheduler
    scheduler = BlockingScheduler()

    # Schedule price collection
    scheduler.add_job(
        collect_prices,
        trigger=IntervalTrigger(seconds=config.POLL_INTERVAL_SECONDS),
        id='price_collection',
        name='Collect prices and detect opportunities',
        replace_existing=True
    )

    logger.info(f"Scheduler configured: polling every {config.POLL_INTERVAL_SECONDS}s")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Goodbye!")

if __name__ == '__main__':
    main()
