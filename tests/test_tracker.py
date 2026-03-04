"""
Unit tests for OpportunityTracker state machine.

The src.database module is patched to an in-memory SQLite instance by
conftest.py before this file is imported — no direct patching needed here.
"""

import unittest
from datetime import datetime

# conftest.py has already patched src.database and created all tables.
from src.models import MatchedContract, Opportunity, Base as ModelsBase
from src.tracker import OpportunityTracker

# Re-use the engine and session factory from conftest via the stub already in sys.modules
import sys
_db_stub = sys.modules['src.database']
TEST_ENGINE = _db_stub.engine
_test_db_session = _db_stub.get_db_session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SPREAD_OPEN = {
    'raw_spread': 0.15,
    'fee_adjusted_spread': 0.06,
    'kalshi_prob': 0.65,
    'polymarket_prob': 0.80,
}

SPREAD_COLLAPSED = {
    'raw_spread': 0.005,
    'fee_adjusted_spread': -0.085,
    'kalshi_prob': 0.70,
    'polymarket_prob': 0.705,
}

SPREAD_UPDATED = {
    'raw_spread': 0.20,
    'fee_adjusted_spread': 0.11,
    'kalshi_prob': 0.60,
    'polymarket_prob': 0.80,
}


def _insert_contract() -> int:
    """Insert a MatchedContract and return its id."""
    with _test_db_session() as session:
        contract = MatchedContract(
            kalshi_id='KALSHI-TEST-1',
            polymarket_id='poly-test-1',
            event_title='Test Event',
            match_score=95.0,
            verified=True,
            active=True,
        )
        session.add(contract)
        session.flush()
        return contract.id


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
class TestOpportunityTrackerFlagOpportunity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Tables are already created by conftest.py — nothing to do here.
        pass

    @classmethod
    def tearDownClass(cls):
        # Leave tables intact so other test modules can use them.
        pass

    def setUp(self):
        """Wipe tables before each test for isolation."""
        with _test_db_session() as session:
            session.query(Opportunity).delete()
            session.query(MatchedContract).delete()

    # --- flag_opportunity ---------------------------------------------------

    def test_flag_creates_open_opportunity(self):
        """flag_opportunity must create a row with status='open'."""
        contract_id = _insert_contract()
        tracker = OpportunityTracker()
        opp_id = tracker.flag_opportunity(contract_id, SPREAD_OPEN)

        with _test_db_session() as session:
            opp = session.get(Opportunity, opp_id)
            self.assertIsNotNone(opp)
            self.assertEqual(opp.status, 'open')

    def test_flag_stores_correct_spread_values(self):
        """flag_opportunity must persist the raw and fee-adjusted spreads."""
        contract_id = _insert_contract()
        opp_id = OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)

        with _test_db_session() as session:
            opp = session.get(Opportunity, opp_id)
            raw = float(opp.raw_spread)
            fee_adj = float(opp.fee_adjusted_spread)

        self.assertAlmostEqual(raw, SPREAD_OPEN['raw_spread'], places=5)
        self.assertAlmostEqual(fee_adj, SPREAD_OPEN['fee_adjusted_spread'], places=5)

    def test_flag_is_idempotent(self):
        """Calling flag_opportunity twice for the same contract must not duplicate open rows."""
        contract_id = _insert_contract()
        tracker = OpportunityTracker()
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)

        with _test_db_session() as session:
            count = session.query(Opportunity).filter_by(
                contract_id=contract_id, status='open'
            ).count()
        self.assertEqual(count, 1)

    def test_flag_updates_peak_when_spread_increases(self):
        """A second flag call with a larger spread must update peak_spread."""
        contract_id = _insert_contract()
        tracker = OpportunityTracker()
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)
        tracker.flag_opportunity(contract_id, SPREAD_UPDATED)

        with _test_db_session() as session:
            opp = session.query(Opportunity).filter_by(
                contract_id=contract_id, status='open'
            ).first()
            peak = float(opp.peak_spread)

        self.assertAlmostEqual(peak, SPREAD_UPDATED['raw_spread'], places=5)

    def test_flag_increments_decay_observations(self):
        """Each flag call on an existing open opportunity must increment decay_observations."""
        contract_id = _insert_contract()
        tracker = OpportunityTracker()
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)

        with _test_db_session() as session:
            opp = session.query(Opportunity).filter_by(
                contract_id=contract_id, status='open'
            ).first()
            obs = opp.decay_observations

        self.assertEqual(obs, 2)

    # --- update_open_opportunities ------------------------------------------

    def test_update_closes_when_spread_collapses(self):
        """update_open_opportunities must close an opportunity whose spread drops below threshold."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)
        OpportunityTracker().update_open_opportunities({contract_id: SPREAD_COLLAPSED})

        with _test_db_session() as session:
            status = session.query(Opportunity).filter_by(contract_id=contract_id).first().status
        self.assertEqual(status, 'closed')

    def test_update_records_close_time(self):
        """Closed opportunity must have a non-null close_time."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)
        OpportunityTracker().update_open_opportunities({contract_id: SPREAD_COLLAPSED})

        with _test_db_session() as session:
            close_time = session.query(Opportunity).filter_by(contract_id=contract_id).first().close_time
        self.assertIsNotNone(close_time)

    def test_update_records_closing_probabilities(self):
        """Closing probabilities must be persisted when an opportunity closes."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)
        OpportunityTracker().update_open_opportunities({contract_id: SPREAD_COLLAPSED})

        with _test_db_session() as session:
            opp = session.query(Opportunity).filter_by(contract_id=contract_id).first()
            k_close = float(opp.kalshi_prob_close)
            p_close = float(opp.polymarket_prob_close)

        self.assertAlmostEqual(k_close, SPREAD_COLLAPSED['kalshi_prob'], places=4)
        self.assertAlmostEqual(p_close, SPREAD_COLLAPSED['polymarket_prob'], places=4)

    def test_update_keeps_open_when_spread_still_above_threshold(self):
        """Opportunity must remain open when spread is still above threshold."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)
        OpportunityTracker().update_open_opportunities({contract_id: SPREAD_OPEN})

        with _test_db_session() as session:
            status = session.query(Opportunity).filter_by(contract_id=contract_id).first().status
        self.assertEqual(status, 'open')

    def test_update_raises_peak_when_spread_grows(self):
        """update_open_opportunities must update peak_spread when a new high is seen."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)
        OpportunityTracker().update_open_opportunities({contract_id: SPREAD_UPDATED})

        with _test_db_session() as session:
            peak = float(session.query(Opportunity).filter_by(contract_id=contract_id).first().peak_spread)
        self.assertAlmostEqual(peak, SPREAD_UPDATED['raw_spread'], places=5)    # --- expire_stale_opportunities -----------------------------------------

    def test_expire_marks_old_open_opportunities(self):
        """Opportunities open longer than max_age_hours must be marked 'expired'."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)

        # Back-date open_time so it appears stale
        with _test_db_session() as session:
            opp = session.query(Opportunity).filter_by(contract_id=contract_id).first()
            opp.open_time = datetime(2000, 1, 1)  # clearly in the past, tz-naive

        OpportunityTracker().expire_stale_opportunities(max_age_hours=1)

        with _test_db_session() as session:
            status = session.query(Opportunity).filter_by(contract_id=contract_id).first().status
        self.assertEqual(status, 'expired')

    def test_expire_does_not_affect_recent_opportunities(self):
        """Recently opened opportunities must not be expired."""
        contract_id = _insert_contract()
        OpportunityTracker().flag_opportunity(contract_id, SPREAD_OPEN)
        OpportunityTracker().expire_stale_opportunities(max_age_hours=24)

        with _test_db_session() as session:
            status = session.query(Opportunity).filter_by(contract_id=contract_id).first().status
        self.assertEqual(status, 'open')

    # --- get_statistics -----------------------------------------------------

    def test_get_statistics_counts_correctly(self):
        """get_statistics must reflect the correct open/closed/total counts."""
        contract_id = _insert_contract()
        tracker = OpportunityTracker()
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)
        tracker.update_open_opportunities({contract_id: SPREAD_COLLAPSED})

        stats = tracker.get_statistics()
        self.assertEqual(stats['total_opportunities'], 1)
        self.assertEqual(stats['open_opportunities'], 0)
        self.assertEqual(stats['closed_opportunities'], 1)

    def test_get_statistics_no_timezone_error(self):
        """get_statistics must not raise TypeError on naive/aware datetime subtraction."""
        contract_id = _insert_contract()
        tracker = OpportunityTracker()
        tracker.flag_opportunity(contract_id, SPREAD_OPEN)
        tracker.update_open_opportunities({contract_id: SPREAD_COLLAPSED})

        # Should complete without raising
        stats = tracker.get_statistics()
        self.assertGreaterEqual(stats['average_duration_seconds'], 0)

    def test_get_statistics_empty_database(self):
        """get_statistics must return zero values when no opportunities exist."""
        stats = OpportunityTracker().get_statistics()
        self.assertEqual(stats['total_opportunities'], 0)
        self.assertEqual(stats['average_duration_seconds'], 0)
        self.assertEqual(stats['average_peak_spread'], 0)


if __name__ == '__main__':
    unittest.main()
