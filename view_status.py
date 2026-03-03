"""
Database visualization and statistics utility.
Run this to see current system state and data quality.
"""

from datetime import datetime, timedelta
from sqlalchemy import func, text
from src.database import get_db_session
from src.models import MatchedContract, Price, Opportunity, BayesianState, APIHealth

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def show_database_stats():
    """Show overall database statistics."""
    print_section("DATABASE STATISTICS")
    
    with get_db_session() as session:
        # Table counts
        print(f"\nMatched Contracts: {session.query(MatchedContract).count()}")
        print(f"  - Active: {session.query(MatchedContract).filter_by(active=True).count()}")
        print(f"  - Verified: {session.query(MatchedContract).filter_by(verified=True).count()}")
        
        print(f"\nPrice Observations: {session.query(Price).count():,}")
        print(f"  - Kalshi: {session.query(Price).filter_by(platform='kalshi').count():,}")
        print(f"  - Polymarket: {session.query(Price).filter_by(platform='polymarket').count():,}")
        
        print(f"\nOpportunities: {session.query(Opportunity).count()}")
        print(f"  - Open: {session.query(Opportunity).filter_by(status='open').count()}")
        print(f"  - Closed: {session.query(Opportunity).filter_by(status='closed').count()}")
        print(f"  - Expired: {session.query(Opportunity).filter_by(status='expired').count()}")

def show_top_matches():
    """Show highest confidence matches."""
    print_section("TOP 10 MATCHED CONTRACTS")
    
    with get_db_session() as session:
        matches = session.query(MatchedContract).order_by(
            MatchedContract.match_score.desc()
        ).limit(10).all()
        
        print(f"\n{'Score':<6} {'Status':<10} {'Event Title':<50}")
        print("-"*70)
        
        for m in matches:
            status = "✓ Verified" if m.verified else "⏳ Pending"
            if not m.active:
                status = "✗ Inactive"
            print(f"{m.match_score:5.1f}  {status:<10} {m.event_title[:50]}")

def show_recent_opportunities():
    """Show recent arbitrage opportunities."""
    print_section("RECENT OPPORTUNITIES (Last 10)")
    
    with get_db_session() as session:
        opps = session.query(Opportunity).order_by(
            Opportunity.open_time.desc()
        ).limit(10).all()
        
        if not opps:
            print("\nNo opportunities detected yet.")
            return
        
        print(f"\n{'Status':<8} {'Spread':<8} {'Duration':<10} {'Event':<40}")
        print("-"*70)
        
        for opp in opps:
            contract = session.query(MatchedContract).get(opp.contract_id)
            
            if opp.close_time and opp.status == 'closed':
                duration = (opp.close_time - opp.open_time).total_seconds()
                duration_str = f"{duration:.0f}s"
            else:
                duration = (datetime.utcnow() - opp.open_time).total_seconds()
                duration_str = f"{duration:.0f}s*"
            
            status_emoji = {
                'open': '🔴',
                'closed': '✅',
                'expired': '⏰'
            }.get(opp.status, '?')
            
            print(
                f"{status_emoji} {opp.status:<6} "
                f"{float(opp.peak_spread)*100:5.2f}%  "
                f"{duration_str:<10} "
                f"{contract.event_title[:40]}"
            )

def show_api_health():
    """Show API health status."""
    print_section("API HEALTH STATUS")
    
    with get_db_session() as session:
        health = session.query(APIHealth).all()
        
        for h in health:
            status_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'down': '❌'
            }.get(h.status, '?')
            
            print(f"\n{h.platform.upper()}: {status_emoji} {h.status}")
            
            if h.last_successful_call:
                last_success = datetime.utcnow() - h.last_successful_call
                print(f"  Last successful: {last_success.total_seconds():.0f}s ago")
            
            if h.consecutive_failures > 0:
                print(f"  Consecutive failures: {h.consecutive_failures}")
                if h.error_message:
                    print(f"  Last error: {h.error_message[:60]}...")

def show_opportunity_stats():
    """Show opportunity statistics."""
    print_section("OPPORTUNITY STATISTICS")
    
    with get_db_session() as session:
        closed = session.query(Opportunity).filter_by(status='closed').all()
        
        if not closed:
            print("\nNo closed opportunities yet. Need more data.")
            return
        
        durations = [
            (opp.close_time - opp.open_time).total_seconds()
            for opp in closed if opp.close_time
        ]
        
        peaks = [float(opp.peak_spread) for opp in closed]
        
        if durations:
            print(f"\nAverage Duration: {sum(durations)/len(durations):.1f}s")
            print(f"Median Duration: {sorted(durations)[len(durations)//2]:.1f}s")
            print(f"Min Duration: {min(durations):.1f}s")
            print(f"Max Duration: {max(durations):.1f}s")
            print(f"Edge Half-Life: {sum(durations)/len(durations)/2:.1f}s")
        
        if peaks:
            print(f"\nAverage Peak Spread: {sum(peaks)/len(peaks)*100:.2f}%")
            print(f"Max Peak Spread: {max(peaks)*100:.2f}%")
            print(f"Min Peak Spread: {min(peaks)*100:.2f}%")

def show_data_freshness():
    """Show how fresh the data is."""
    print_section("DATA FRESHNESS")
    
    with get_db_session() as session:
        latest_price = session.query(Price).order_by(
            Price.timestamp.desc()
        ).first()
        
        if latest_price:
            age = datetime.utcnow() - latest_price.timestamp
            print(f"\nLatest price observation: {age.total_seconds():.0f}s ago")
            print(f"Platform: {latest_price.platform}")
            
            # Count recent observations
            last_5min = datetime.utcnow() - timedelta(minutes=5)
            recent = session.query(Price).filter(
                Price.timestamp >= last_5min
            ).count()
            
            print(f"Observations in last 5 minutes: {recent}")
        else:
            print("\nNo price data yet. Start the scheduler!")

def main():
    """Run all visualizations."""
    print("\n" + "🎯 PREDICTION MARKET ARBITRAGE SYSTEM" + "\n")
    print(f"Report generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        show_database_stats()
        show_api_health()
        show_data_freshness()
        show_top_matches()
        show_recent_opportunities()
        show_opportunity_stats()
        
        print("\n" + "="*60)
        print("✅ Report complete!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        print("Make sure the database is initialized and scheduler has run.")

if __name__ == '__main__':
    main()
