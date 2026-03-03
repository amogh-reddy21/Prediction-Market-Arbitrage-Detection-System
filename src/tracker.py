"""Arbitrage opportunity tracker with edge decay analysis."""

from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from loguru import logger

from .config import config
from .database import get_db_session
from .models import Opportunity, Price, MatchedContract

class OpportunityTracker:
    """Track arbitrage opportunities and edge decay over time."""
    
    def flag_opportunity(
        self,
        contract_id: int,
        spread_data: Dict[str, float]
    ) -> int:
        """
        Flag a new arbitrage opportunity.
        
        Args:
            contract_id: MatchedContract ID
            spread_data: Spread calculation from BayesianEngine
            
        Returns:
            Opportunity ID
        """
        with get_db_session() as session:
            # Check if already have an open opportunity for this contract
            existing = session.query(Opportunity).filter_by(
                contract_id=contract_id,
                status='open'
            ).first()
            
            if existing:
                # Update existing opportunity if spread increased
                if spread_data['raw_spread'] > float(existing.peak_spread):
                    existing.peak_spread = spread_data['raw_spread']
                    existing.peak_time = datetime.now(timezone.utc)
                
                existing.decay_observations += 1
                session.commit()
                return existing.id
            
            # Create new opportunity
            now = datetime.now(timezone.utc)
            opportunity = Opportunity(
                contract_id=contract_id,
                open_time=now,
                raw_spread=spread_data['raw_spread'],
                fee_adjusted_spread=spread_data['fee_adjusted_spread'],
                kalshi_prob_open=spread_data['kalshi_prob'],
                polymarket_prob_open=spread_data['polymarket_prob'],
                peak_spread=spread_data['raw_spread'],
                peak_time=now,
                decay_observations=1,
                status='open'
            )
            
            session.add(opportunity)
            session.commit()
            
            logger.info(
                f"🚨 New opportunity flagged: Contract {contract_id}, "
                f"spread={spread_data['fee_adjusted_spread']:.4f}"
            )
            
            return opportunity.id
    
    def update_open_opportunities(self, current_spreads: Dict[int, Dict[str, float]]):
        """
        Update all open opportunities with current spread data.
        
        Args:
            current_spreads: Dict mapping contract_id to spread_data
        """
        with get_db_session() as session:
            open_opps = session.query(Opportunity).filter_by(status='open').all()
            
            closed_count = 0
            
            for opp in open_opps:
                spread_data = current_spreads.get(opp.contract_id)
                
                if not spread_data:
                    # No current data, skip
                    continue
                
                # Update observation count
                opp.decay_observations += 1
                
                # Check if spread has closed below threshold
                if spread_data['fee_adjusted_spread'] < config.MIN_SPREAD_THRESHOLD:
                    # Close the opportunity
                    now = datetime.now(timezone.utc)
                    opp.close_time = now
                    opp.status = 'closed'
                    opp.kalshi_prob_close = spread_data['kalshi_prob']
                    opp.polymarket_prob_close = spread_data['polymarket_prob']

                    # Calculate duration — strip tz if open_time is naive (SQLite)
                    open_time = opp.open_time
                    if open_time.tzinfo is None:
                        now_naive = now.replace(tzinfo=None)
                        duration = (now_naive - open_time).total_seconds()
                    else:
                        duration = (now - open_time).total_seconds()
                    
                    logger.info(
                        f"✓ Opportunity closed: Contract {opp.contract_id}, "
                        f"duration={duration:.0f}s, peak={float(opp.peak_spread):.4f}"
                    )
                    
                    closed_count += 1
                else:
                    # Still open, check for new peak
                    if spread_data['raw_spread'] > float(opp.peak_spread):
                        opp.peak_spread = spread_data['raw_spread']
                        opp.peak_time = datetime.now(timezone.utc)
            
            session.commit()
            
            if closed_count > 0:
                logger.info(f"Closed {closed_count} opportunities in this update")
    
    def expire_stale_opportunities(self, max_age_hours: int = 24):
        """
        Mark stale opportunities as expired.
        
        Args:
            max_age_hours: Maximum age before expiring (default 24 hours)
        """
        with get_db_session() as session:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            
            stale_opps = session.query(Opportunity).filter(
                Opportunity.status == 'open',
                Opportunity.open_time < cutoff_time
            ).all()
            
            for opp in stale_opps:
                opp.status = 'expired'
                opp.close_time = datetime.now(timezone.utc)
            
            session.commit()
            
            if stale_opps:
                logger.warning(f"Expired {len(stale_opps)} stale opportunities")
    
    def get_decay_curve(self, opportunity_id: int) -> List[Dict]:
        """
        Get decay curve for a specific opportunity.
        
        Args:
            opportunity_id: Opportunity ID
            
        Returns:
            List of {timestamp, spread} dictionaries
        """
        with get_db_session() as session:
            opp = session.get(Opportunity, opportunity_id)

            if not opp:
                return []

            # Get price history during opportunity window
            query = session.query(Price).filter(
                Price.contract_id == opp.contract_id,
                Price.timestamp >= opp.open_time
            )
            if opp.close_time:
                query = query.filter(Price.timestamp <= opp.close_time)
            prices = query.order_by(Price.timestamp).all()

            # Group by timestamp using a dict — O(n) instead of O(n²)
            by_ts: dict = {}
            for p in prices:
                by_ts.setdefault(p.timestamp, {})[p.platform] = p

            decay_curve = []
            for ts in sorted(by_ts):
                row = by_ts[ts]
                if 'kalshi' in row and 'polymarket' in row:
                    spread = abs(
                        float(row['polymarket'].probability) - float(row['kalshi'].probability)
                    )
                    decay_curve.append({'timestamp': ts, 'spread': spread})

            return decay_curve
    
    def get_statistics(self) -> Dict:
        """
        Get overall opportunity statistics.
        
        Returns:
            Dictionary with aggregate statistics
        """
        with get_db_session() as session:
            total_opps = session.query(Opportunity).count()
            open_opps = session.query(Opportunity).filter_by(status='open').count()
            closed_opps = session.query(Opportunity).filter_by(status='closed').count()
            
            # Average duration for closed opportunities
            closed = session.query(Opportunity).filter_by(status='closed').all()
            
            if closed:
                durations = []
                for opp in closed:
                    if not opp.close_time:
                        continue
                    close_t, open_t = opp.close_time, opp.open_time
                    # Normalise: if one side is naive, strip tz from the other
                    if close_t.tzinfo is not None and open_t.tzinfo is None:
                        close_t = close_t.replace(tzinfo=None)
                    elif open_t.tzinfo is not None and close_t.tzinfo is None:
                        open_t = open_t.replace(tzinfo=None)
                    durations.append((close_t - open_t).total_seconds())
                avg_duration = sum(durations) / len(durations) if durations else 0
                avg_peak = sum(float(opp.peak_spread) for opp in closed) / len(closed)
            else:
                avg_duration = 0
                avg_peak = 0
            
            return {
                'total_opportunities': total_opps,
                'open_opportunities': open_opps,
                'closed_opportunities': closed_opps,
                'average_duration_seconds': avg_duration,
                'average_peak_spread': avg_peak,
                'edge_half_life': avg_duration / 2 if avg_duration > 0 else 0  # Simplified
            }
    
    def get_recent_opportunities(self, limit: int = 50) -> List[Opportunity]:
        """
        Get recent opportunities sorted by open time.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of Opportunity objects
        """
        with get_db_session() as session:
            opps = session.query(Opportunity).order_by(
                Opportunity.open_time.desc()
            ).limit(limit).all()
            
            # Detach from session
            session.expunge_all()
            
            return opps
