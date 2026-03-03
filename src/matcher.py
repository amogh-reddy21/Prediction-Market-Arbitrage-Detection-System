"""Contract matching engine using fuzzy string matching."""

import re
from rapidfuzz import fuzz, process
from typing import List, Dict, Optional, Tuple
from loguru import logger
from datetime import datetime, timezone

from .config import config
from .database import get_db_session
from .models import MatchedContract

class ContractMatcher:
    """Fuzzy matching to pair contracts across platforms."""
    
    def __init__(self, threshold: float = None):
        """
        Initialize matcher.
        
        Args:
            threshold: Minimum similarity score (0-100). Default from config.
        """
        self.threshold = threshold or config.FUZZY_MATCH_THRESHOLD
        
    def normalize_title(self, title: str) -> str:
        """
        Normalize contract title for better matching.

        Args:
            title: Raw contract title

        Returns:
            Normalized title
        """
        title = title.lower()

        # Remove punctuation
        title = re.sub(r'[?!.,]', '', title)

        # Remove stop words as whole words only (not substrings)
        stop_words = r'\b(will|does|is|are|yes or no|true or false)\b'
        title = re.sub(stop_words, '', title)

        # Remove trailing platform markers
        title = re.sub(r'\s*-\s*(yes|no)\s*$', '', title)

        # Collapse whitespace
        title = ' '.join(title.split())

        return title.strip()
    
    def find_matches(
        self, 
        kalshi_markets: List[Dict], 
        polymarket_markets: List[Dict]
    ) -> List[Tuple[Dict, Dict, float]]:
        """
        Find matching contracts between platforms.
        
        Args:
            kalshi_markets: List of Kalshi markets
            polymarket_markets: List of Polymarket markets
            
        Returns:
            List of (kalshi_market, polymarket_market, score) tuples
        """
        matches = []
        
        # Create lookup dict for Polymarket
        poly_dict = {
            self.normalize_title(m.get('question', m.get('title', ''))): m 
            for m in polymarket_markets
        }
        poly_titles = list(poly_dict.keys())
        
        for kalshi_market in kalshi_markets:
            # Kalshi uses 'title', Polymarket uses 'question' or 'title'
            kalshi_title = self.normalize_title(kalshi_market.get('title', ''))
            
            # Find best match using token_sort_ratio (handles word order differences)
            result = process.extractOne(
                kalshi_title,
                poly_titles,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self.threshold
            )
            
            if result:
                matched_title, score, _ = result
                poly_market = poly_dict[matched_title]
                
                matches.append((kalshi_market, poly_market, score))
                
                logger.debug(
                    f"Match found (score={score:.1f}): "
                    f"'{kalshi_market.get('title', '')[:50]}...' <-> "
                    f"'{poly_market.get('question', poly_market.get('title', ''))[:50]}...'"
                )
        
        logger.info(f"Found {len(matches)} contract matches above threshold {self.threshold}")
        return matches
    
    def save_matches(self, matches: List[Tuple[Dict, Dict, float]], verified: bool = False):
        """
        Save matched contracts to database.
        
        Args:
            matches: List of (kalshi_market, polymarket_market, score) tuples
            verified: Whether matches have been manually verified
        """
        saved_count = 0
        
        with get_db_session() as session:
            for kalshi, poly, score in matches:
                # Check if match already exists
                existing = session.query(MatchedContract).filter_by(
                    kalshi_id=kalshi['id'],
                    polymarket_id=poly['id']
                ).first()
                
                if existing:
                    # Update score if improved
                    if score > existing.match_score:
                        existing.match_score = score
                        existing.updated_at = datetime.now(timezone.utc)
                    continue
                
                # Create new match
                match = MatchedContract(
                    kalshi_id=kalshi['id'],
                    polymarket_id=poly['id'],
                    event_title=kalshi.get('title', 'Unknown'),  # Use title instead of event_slug
                    match_score=score,
                    verified=verified,
                    active=True
                )
                
                session.add(match)
                saved_count += 1
            
            session.commit()
        
        logger.info(f"✓ Saved {saved_count} new matched contracts to database")
    
    def get_active_matches(self) -> List[MatchedContract]:
        """
        Retrieve all active matched contracts from database.
        
        Returns:
            List of MatchedContract objects
        """
        with get_db_session() as session:
            matches = session.query(MatchedContract).filter_by(active=True).all()
            
            # Detach from session
            session.expunge_all()
            
            return matches
    
    def manual_verify(self, contract_id: int, verified: bool = True):
        """
        Manually verify or reject a match.
        
        Args:
            contract_id: MatchedContract ID
            verified: Verification status
        """
        with get_db_session() as session:
            match = session.get(MatchedContract, contract_id)
            if match:
                match.verified = verified
                session.commit()
                logger.info(f"Contract {contract_id} verification set to {verified}")
    
    def deactivate_match(self, contract_id: int):
        """
        Deactivate a matched contract (stop monitoring).
        
        Args:
            contract_id: MatchedContract ID
        """
        with get_db_session() as session:
            match = session.get(MatchedContract, contract_id)
            if match:
                match.active = False
                session.commit()
                logger.info(f"Contract {contract_id} deactivated")
