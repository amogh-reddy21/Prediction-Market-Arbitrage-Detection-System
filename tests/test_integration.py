"""
Integration test: full pipeline using an in-memory SQLite database.

Mocks both API clients so no network calls are made.
Runs: match → Bayesian update → opportunity detection → tracker update.

The src.database module is patched to an in-memory SQLite instance by
conftest.py before this file is imported.
"""

import sys
import unittest
from unittest.mock import patch

# conftest.py has already patched src.database — pull the shared helpers from it.
_db_stub = sys.modules['src.database']
TEST_ENGINE = _db_stub.engine
_test_db_session = _db_stub.get_db_session

# Safe to import src modules
from src.models import MatchedContract, Price, Opportunity, BayesianState, Base as ModelsBase
from src.matcher import ContractMatcher
from src.bayesian import BayesianEngine
from src.tracker import OpportunityTracker

KALSHI_MARKETS = [
    {
        'platform': 'kalshi',
        'id': 'KALSHI-BTC-100K',
        'title': 'Will Bitcoin reach $100k by end of 2025?',
        'probability': 0.65,
        'yes_bid': 0.63,
        'yes_ask': 0.67,
        'volume': 50000,
        'open_interest': 10000,
        'close_time': None,
        'raw': {}
    }
]

POLY_MARKETS = [
    {
        'platform': 'polymarket',
        'id': 'poly-btc-100k',
        'title': 'Bitcoin reaches $100k in 2025',
        'question': 'Bitcoin reaches $100k in 2025',
        'probability': 0.80,
        'yes_bid': 0.78,
        'yes_ask': 0.82,
        'volume': 30000,
        'open_interest': 8000,
        'close_time': None,
        'raw': {}
    }
]


class TestFullPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Tables are already created by conftest.py — nothing to do here."""
        pass

    @classmethod
    def tearDownClass(cls):
        """Leave tables intact for other test modules that share the engine."""
        pass

    def setUp(self):
        """Clear all rows before each test for isolation."""
        with _test_db_session() as session:
            session.query(BayesianState).delete()
            session.query(Price).delete()
            session.query(Opportunity).delete()
            session.query(MatchedContract).delete()

    # ------------------------------------------------------------------
    # 1. Matcher tests
    # ------------------------------------------------------------------

    def test_normalize_title_whole_word_only(self):
        """normalize_title must not corrupt words containing stop-word substrings."""
        matcher = ContractMatcher()
        # "dismiss" contains "is" — must NOT become "dm"
        result = matcher.normalize_title("Will dismiss the case?")
        self.assertIn('dismiss', result, "normalize_title stripped 'is' from inside 'dismiss'")

    def test_fuzzy_matching_finds_equivalent_contracts(self):
        """Matcher should pair the Kalshi and Polymarket BTC contracts."""
        matcher = ContractMatcher(threshold=60.0)
        matches = matcher.find_matches(KALSHI_MARKETS, POLY_MARKETS)
        self.assertEqual(len(matches), 1)
        k, p, score = matches[0]
        self.assertEqual(k['id'], 'KALSHI-BTC-100K')
        self.assertEqual(p['id'], 'poly-btc-100k')
        self.assertGreaterEqual(score, 60.0)

    def test_save_matches_persists_to_db(self):
        """save_matches should write a MatchedContract row."""
        matcher = ContractMatcher(threshold=60.0)
        matches = matcher.find_matches(KALSHI_MARKETS, POLY_MARKETS)
        matcher.save_matches(matches)

        with _test_db_session() as session:
            count = session.query(MatchedContract).count()
        self.assertEqual(count, 1)

    def test_save_matches_is_idempotent(self):
        """Calling save_matches twice must not duplicate rows."""
        matcher = ContractMatcher(threshold=60.0)
        matches = matcher.find_matches(KALSHI_MARKETS, POLY_MARKETS)
        matcher.save_matches(matches)
        matcher.save_matches(matches)

        with _test_db_session() as session:
            count = session.query(MatchedContract).count()
        self.assertEqual(count, 1)

    # ------------------------------------------------------------------
    # 2. Bayesian engine tests
    # ------------------------------------------------------------------

    def test_bayesian_update_creates_state(self):
        """update_posterior should persist a BayesianState row."""
        matcher = ContractMatcher(threshold=60.0)
        matches = matcher.find_matches(KALSHI_MARKETS, POLY_MARKETS)
        matcher.save_matches(matches)

        with _test_db_session() as session:
            contract_id = session.query(MatchedContract).first().id

        engine = BayesianEngine(window_size=5)
        prob = engine.update_posterior(contract_id, 'kalshi', 0.65)

        self.assertIsInstance(prob, float)
        self.assertGreater(prob, 0.0)
        self.assertLess(prob, 1.0)

        with _test_db_session() as session:
            state = session.query(BayesianState).filter_by(
                contract_id=contract_id, platform='kalshi'
            ).first()
        self.assertIsNotNone(state)

    def test_compute_spread_preserves_negative(self):
        """fee_adjusted_spread must be negative when spread < combined fees (no silent floor)."""
        engine = BayesianEngine(window_size=5)
        # Tiny spread (0.01) is well below combined fees (~0.09)
        spread_data = engine.compute_spread(1, 0.50, 0.51, use_bayesian=False)
        self.assertLess(
            spread_data['fee_adjusted_spread'], 0,
            "fee_adjusted_spread should be negative when spread < fees"
        )

    def test_is_opportunity_respects_threshold(self):
        """is_opportunity must return False for sub-threshold spreads."""
        engine = BayesianEngine()
        below = {'fee_adjusted_spread': 0.001}
        above = {'fee_adjusted_spread': 0.10}
        self.assertFalse(engine.is_opportunity(below))
        self.assertTrue(engine.is_opportunity(above))

    # ------------------------------------------------------------------
    # 3. Tracker tests
    # ------------------------------------------------------------------

    def _setup_contract_and_opportunity(self):
        """Helper: insert a contract and flag an opportunity, return contract_id."""
        matcher = ContractMatcher(threshold=60.0)
        matches = matcher.find_matches(KALSHI_MARKETS, POLY_MARKETS)
        matcher.save_matches(matches)

        with _test_db_session() as session:
            contract_id = session.query(MatchedContract).first().id

        spread_data = {
            'raw_spread': 0.15,
            'fee_adjusted_spread': 0.06,
            'kalshi_prob': 0.65,
            'polymarket_prob': 0.80,
        }
        tracker = OpportunityTracker()
        opp_id = tracker.flag_opportunity(contract_id, spread_data)
        return contract_id, opp_id

    def test_flag_opportunity_creates_row(self):
        """flag_opportunity should write an Opportunity row with status='open'."""
        _, opp_id = self._setup_contract_and_opportunity()
        with _test_db_session() as session:
            opp = session.get(Opportunity, opp_id)
            self.assertIsNotNone(opp)
            self.assertEqual(opp.status, 'open')

    def test_flag_opportunity_is_idempotent(self):
        """Flagging the same contract twice must not create duplicate open rows."""
        contract_id, _ = self._setup_contract_and_opportunity()
        spread_data = {
            'raw_spread': 0.15,
            'fee_adjusted_spread': 0.06,
            'kalshi_prob': 0.65,
            'polymarket_prob': 0.80,
        }
        OpportunityTracker().flag_opportunity(contract_id, spread_data)

        with _test_db_session() as session:
            count = session.query(Opportunity).filter_by(
                contract_id=contract_id, status='open'
            ).count()
        self.assertEqual(count, 1)

    def test_update_closes_opportunity_when_spread_collapses(self):
        """update_open_opportunities should close an opportunity when spread drops below threshold."""
        contract_id, _ = self._setup_contract_and_opportunity()

        collapsed_spread = {
            'raw_spread': 0.005,
            'fee_adjusted_spread': -0.085,   # now negative → below threshold
            'kalshi_prob': 0.70,
            'polymarket_prob': 0.71,
        }
        OpportunityTracker().update_open_opportunities({contract_id: collapsed_spread})

        with _test_db_session() as session:
            opp = session.query(Opportunity).filter_by(contract_id=contract_id).first()
            self.assertEqual(opp.status, 'closed')

    def test_get_statistics_duration_no_timezone_error(self):
        """get_statistics should not raise a TypeError on naive/aware datetime subtraction."""
        contract_id, _ = self._setup_contract_and_opportunity()

        # Close it so there's a closed opportunity for statistics to compute duration on
        collapsed_spread = {
            'raw_spread': 0.005,
            'fee_adjusted_spread': -0.085,
            'kalshi_prob': 0.70,
            'polymarket_prob': 0.71,
        }
        OpportunityTracker().update_open_opportunities({contract_id: collapsed_spread})

        # Should not raise TypeError regardless of tz-naive SQLite datetimes
        stats = OpportunityTracker().get_statistics()
        self.assertEqual(stats['closed_opportunities'], 1)
        self.assertGreaterEqual(stats['average_duration_seconds'], 0)
        self.assertGreater(stats['average_peak_spread'], 0)


if __name__ == '__main__':
    unittest.main()
