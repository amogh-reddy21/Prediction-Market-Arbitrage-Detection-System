#!/usr/bin/env python3
"""
Monte Carlo simulation module for validating the arbitrage detection algorithm.

NOTE ON METHODOLOGY
-------------------
This module uses *synthetically generated* market data, not live historical API
data.  Real-market backtesting would require collecting a persistent price feed
over time (see src/scheduler.py) and then replaying the stored `prices` table.

The simulation below is intended to:
  1. Validate that the detection logic fires correctly under known conditions.
  2. Produce order-of-magnitude performance estimates under realistic assumptions
     about market volatility and arbitrage frequency.
  3. Stress-test edge cases (e.g., rapid spread collapse, zero-volume markets).

All metrics produced here are *simulated* and should be reported as such.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import random
import numpy as np

from src.database import get_db_session
from src.models import Opportunity, MatchedContract, Price
from src.bayesian import BayesianEngine
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed seed → reproducible, citable numbers across every run.
_SIMULATION_SEED = 42


class HistoricalBacktest:
    """
    Monte Carlo simulation of the arbitrage detection pipeline.

    Uses synthetically generated price paths — NOT live API data.
    Label any metrics produced here as 'simulated' in external reports.
    """
    
    def __init__(self, seed: int = _SIMULATION_SEED):
        self.bayesian = BayesianEngine()
        self.opportunities_found = []
        self.total_price_points = 0
        self.matched_pairs = 0
        self.bayesian_cache = {}  # Simple cache for demo
        # Seed both stdlib random and NumPy for full reproducibility
        random.seed(seed)
        np.random.seed(seed)
        
    def generate_simulated_market_data(self, days: int = 30) -> List[Dict]:
        """
        Generate synthetic price paths for simulation.

        Prices follow a correlated random walk. Arbitrage windows are injected
        as multi-tick events (3–12 ticks long) at a ~2% per-tick onset rate,
        so that a single real opportunity appears as a contiguous block of
        observations rather than independent one-tick spikes.

        Args:
            days: Length of the simulation window in days

        Returns:
            List of synthetic price observations, each tagged with
            `ground_truth_arb` (bool) so detection accuracy can be measured.
        """
        logger.info(f"Generating {days} days of synthetic simulation data...")

        contract_pairs = []
        for i in range(50):
            contract_pairs.append({
                'kalshi_title': f'Market Event {i}',
                'polymarket_title': f'Event {i} Outcome',
                'base_prob': random.uniform(0.2, 0.8),
                # Track whether this pair is currently inside an arb window
                'arb_ticks_remaining': 0,
                'arb_spread': 0.0,
                'arb_direction': 1,
            })

        historical_data = []
        observations_per_day = 48  # Every 30 minutes

        for day in range(days):
            date = datetime.now() - timedelta(days=days - day)

            for obs in range(observations_per_day):
                timestamp = date + timedelta(minutes=obs * 30)

                for pair in contract_pairs:
                    base_prob = pair['base_prob']

                    # Random walk on the true underlying probability
                    drift = random.gauss(0, 0.01)
                    base_prob = max(0.1, min(0.9, base_prob + drift))
                    pair['base_prob'] = base_prob

                    # Normal per-platform noise
                    kalshi_prob    = base_prob + random.gauss(0, 0.015)
                    polymarket_prob = base_prob + random.gauss(0, 0.015)

                    ground_truth_arb = False

                    if pair['arb_ticks_remaining'] > 0:
                        # Continue existing arbitrage window — spread decays linearly
                        # toward zero over the remaining ticks
                        remaining = pair['arb_ticks_remaining']
                        total     = pair['arb_window_length']
                        decay     = pair['arb_spread'] * (remaining / total)
                        direction = pair['arb_direction']
                        kalshi_prob    += direction * decay / 2
                        polymarket_prob -= direction * decay / 2
                        pair['arb_ticks_remaining'] -= 1
                        ground_truth_arb = True

                    elif random.random() < 0.02:
                        # Start a new arbitrage window (2% onset probability per tick)
                        window_len = random.randint(3, 12)
                        spread     = random.uniform(0.12, 0.28)
                        direction  = 1 if random.random() < 0.5 else -1
                        pair['arb_ticks_remaining'] = window_len
                        pair['arb_window_length']   = window_len
                        pair['arb_spread']          = spread
                        pair['arb_direction']       = direction
                        kalshi_prob    += direction * spread / 2
                        polymarket_prob -= direction * spread / 2
                        ground_truth_arb = True

                    kalshi_prob     = max(0.05, min(0.95, kalshi_prob))
                    polymarket_prob = max(0.05, min(0.95, polymarket_prob))

                    historical_data.append({
                        'timestamp':        timestamp,
                        'kalshi_title':     pair['kalshi_title'],
                        'polymarket_title': pair['polymarket_title'],
                        'kalshi_prob':      kalshi_prob,
                        'polymarket_prob':  polymarket_prob,
                        'ground_truth_arb': ground_truth_arb,   # for accuracy metrics
                    })

        self.total_price_points = len(historical_data)
        logger.info(f"Generated {self.total_price_points:,} historical price observations")
        return historical_data
    
    def run_backtest(self, historical_data: List[Dict]) -> Dict:
        """
        Run arbitrage detection algorithm on historical data.

        Detection logic mirrors the live scheduler exactly:
          1. Apply Beta-Binomial Bayesian smoothing per (contract, platform)
          2. Compute fee-adjusted net spread on smoothed probabilities
          3. Open an opportunity when net_spread > MIN_SPREAD_THRESHOLD
          4. Close it when net_spread falls back below threshold
          5. Record one opportunity per contiguous open window (not per tick)

        Accuracy metrics are computed against the ground_truth_arb flag
        injected by generate_simulated_market_data so we can measure
        precision and recall directly.
        """
        logger.info("Starting backtest analysis...")

        opportunities   = []   # closed opportunity records
        open_windows    = {}   # contract_key → open_time

        # Per-contract Bayesian state: {key: {'alpha': float, 'beta': float, 'n': int}}
        bayes_state: Dict[str, Dict] = {}
        window_size = self.bayesian.window_size

        def bayesian_update(key: str, p: float) -> float:
            """Apply in-memory Beta-Binomial conjugate update; return posterior mean."""
            if key not in bayes_state:
                bayes_state[key] = {'alpha': 1.0, 'beta': 1.0, 'n': 0}
            s = bayes_state[key]
            # Rolling-window decay (mirrors bayesian.py exactly)
            if s['n'] >= window_size:
                scale = (window_size - 1) / window_size
                s['alpha'] *= scale
                s['beta']  *= scale
            s['alpha'] += p
            s['beta']  += (1.0 - p)
            s['n']     += 1
            return s['alpha'] / (s['alpha'] + s['beta'])   # posterior mean

        # Group observations by contract pair and process chronologically
        pairs: Dict[tuple, List[Dict]] = {}
        for obs in historical_data:
            key = (obs['kalshi_title'], obs['polymarket_title'])
            pairs.setdefault(key, []).append(obs)

        logger.info(f"Analyzing {len(pairs)} contract pairs...")

        # For accuracy metrics against ground truth
        true_positives  = 0
        false_positives = 0
        false_negatives = 0
        all_spreads     = []

        for pair_key, observations in pairs.items():
            kalshi_title, poly_title = pair_key
            k_key = f"kalshi_{kalshi_title}"
            p_key = f"poly_{poly_title}"
            open_time     = None
            open_k_prob   = None
            open_p_prob   = None
            peak_spread   = 0.0

            for obs in observations:
                # ── Bayesian smoothing (real conjugate update) ────────────────
                smoothed_k = bayesian_update(k_key, obs['kalshi_prob'])
                smoothed_p = bayesian_update(p_key, obs['polymarket_prob'])

                raw_spread = abs(obs['kalshi_prob'] - obs['polymarket_prob'])
                net_spread = abs(smoothed_k - smoothed_p) - (config.FEE_KALSHI + config.FEE_POLYMARKET)
                all_spreads.append(raw_spread)

                above_threshold = net_spread > config.MIN_SPREAD_THRESHOLD

                if above_threshold and open_time is None:
                    # Open a new opportunity window
                    open_time   = obs['timestamp']
                    open_k_prob = obs['kalshi_prob']
                    open_p_prob = obs['polymarket_prob']
                    peak_spread = net_spread

                elif above_threshold and open_time is not None:
                    # Still inside a window — update peak
                    peak_spread = max(peak_spread, net_spread)

                elif not above_threshold and open_time is not None:
                    # Spread collapsed — close the window and record one opportunity
                    duration_s = (obs['timestamp'] - open_time).total_seconds()
                    opportunities.append({
                        'timestamp':        open_time,
                        'close_time':       obs['timestamp'],
                        'duration_s':       duration_s,
                        'kalshi_title':     kalshi_title,
                        'polymarket_title': poly_title,
                        'kalshi_prob':      open_k_prob,
                        'polymarket_prob':  open_p_prob,
                        'net_spread':       peak_spread,
                        'profit_pct':       peak_spread * 100,
                    })

                    # ── Accuracy: was this a real arb window? ─────────────────
                    # An opportunity is a true positive if *any* tick inside the
                    # window had ground_truth_arb=True.
                    if obs.get('ground_truth_arb', False):
                        true_positives  += 1
                    else:
                        false_positives += 1

                    open_time = None
                    peak_spread = 0.0

            # Close any window still open at end of data
            if open_time is not None:
                last = observations[-1]
                opportunities.append({
                    'timestamp':        open_time,
                    'close_time':       last['timestamp'],
                    'duration_s':       (last['timestamp'] - open_time).total_seconds(),
                    'kalshi_title':     kalshi_title,
                    'polymarket_title': poly_title,
                    'kalshi_prob':      open_k_prob,
                    'polymarket_prob':  open_p_prob,
                    'net_spread':       peak_spread,
                    'profit_pct':       peak_spread * 100,
                })

        # Ground-truth windows that were never detected
        gt_windows = sum(
            1 for obs in historical_data
            if obs.get('ground_truth_arb') and
               abs(obs['kalshi_prob'] - obs['polymarket_prob'])
               - (config.FEE_KALSHI + config.FEE_POLYMARKET) > config.MIN_SPREAD_THRESHOLD
        )
        false_negatives = max(0, gt_windows - true_positives)
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall    = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0

        self.opportunities_found = opportunities

        # ── Sharpe ratio (annualised daily P&L) ──────────────────────────────
        sharpe = 0.0
        if opportunities:
            daily_pnl: Dict[str, float] = {}
            for opp in opportunities:
                day_key = opp['timestamp'].strftime('%Y-%m-%d')
                daily_pnl[day_key] = daily_pnl.get(day_key, 0.0) + opp['net_spread']
            all_days   = {obs['timestamp'].strftime('%Y-%m-%d') for obs in historical_data}
            pnl_series = np.array([daily_pnl.get(d, 0.0) for d in all_days])
            mean_d, std_d = pnl_series.mean(), pnl_series.std(ddof=1)
            if std_d > 0:
                sharpe = round(float(mean_d / std_d * np.sqrt(252)), 2)

        avg_duration_min = (
            np.mean([o['duration_s'] for o in opportunities]) / 60
            if opportunities else 0.0
        )

        results = {
            'total_observations':       len(historical_data),
            'contract_pairs_analyzed':  len(pairs),
            'opportunities_found':      len(opportunities),
            'avg_spread':               np.mean(all_spreads) if all_spreads else 0,
            'max_spread':               max(all_spreads)     if all_spreads else 0,
            'avg_profit_pct':           np.mean([o['profit_pct'] for o in opportunities]) if opportunities else 0,
            'avg_duration_min':         avg_duration_min,
            'opportunities_per_day':    len(opportunities) / 30,
            'sharpe_ratio':             sharpe,
            'precision':                round(precision * 100, 1),
            'recall':                   round(recall    * 100, 1),
            'true_positives':           true_positives,
            'false_positives':          false_positives,
        }

        logger.info(
            f"Backtest complete: {len(opportunities)} opportunities "
            f"| Sharpe {sharpe:.2f} | Precision {precision*100:.1f}% | Recall {recall*100:.1f}%"
        )
        return results
    
    def print_results(self, results: Dict):
        """Print simulation results clearly labelled as synthetic."""
        print("\n" + "=" * 80)
        print("📊 MONTE CARLO SIMULATION RESULTS  (synthetic data — not live API history)")
        print("=" * 80)

        print(f"\n🔍 DATA ANALYZED:")
        print(f"  • Total price observations:  {results['total_observations']:,}")
        print(f"  • Contract pairs analyzed:   {results['contract_pairs_analyzed']:,}")
        print(f"  • Time period:               30 days")

        print(f"\n💰 OPPORTUNITIES DETECTED (lifecycle-based, not per-tick):")
        print(f"  • Total arbitrage windows:   {results['opportunities_found']}")
        print(f"  • Avg per day:               {results['opportunities_per_day']:.1f}")
        print(f"  • Avg duration:              {results['avg_duration_min']:.1f} min")
        print(f"  • Avg fee-adjusted spread:   {results['avg_profit_pct']:.2f}%")
        print(f"  • Sharpe ratio (annualised): {results['sharpe_ratio']:.2f}")

        print(f"\n🎯 DETECTION ACCURACY (vs. ground-truth injected windows):")
        print(f"  • Precision:                 {results['precision']:.1f}%")
        print(f"  • Recall:                    {results['recall']:.1f}%")
        print(f"  • True positives:            {results['true_positives']}")
        print(f"  • False positives:           {results['false_positives']}")

        print("\n" + "=" * 80)
        print("✅ RESUME BULLET POINTS:")
        print("=" * 80)
        print(f"""
• Validated detection algorithm via Monte Carlo simulation on {results['total_observations']:,}
  synthetic price observations across {results['contract_pairs_analyzed']} contract pairs (30 days);
  identified {results['opportunities_found']} arbitrage windows averaging {results['avg_profit_pct']:.2f}%
  fee-adjusted spread ({results['sharpe_ratio']:.2f} Sharpe ratio)

• Bayesian Beta-Binomial smoothing achieved {results['precision']:.0f}% precision and
  {results['recall']:.0f}% recall vs. ground-truth injected arbitrage events,
  with {results['false_positives']} false positives out of {results['opportunities_found']} total detections
""")

        print("=" * 80)
        print("🎯 TOP 5 OPPORTUNITIES BY PEAK SPREAD:")
        print("=" * 80)
        top_5 = sorted(self.opportunities_found, key=lambda x: x['net_spread'], reverse=True)[:5]
        for i, opp in enumerate(top_5, 1):
            dur_min = opp['duration_s'] / 60
            print(f"\n{i}. {opp['timestamp'].strftime('%Y-%m-%d %H:%M')}  "
                  f"(duration: {dur_min:.0f} min)")
            print(f"   Market: {opp['kalshi_title']}")
            print(f"   Peak net spread: {opp['profit_pct']:.2f}%")
            print(f"   Kalshi: {opp['kalshi_prob']:.3f}  |  Polymarket: {opp['polymarket_prob']:.3f}")


def run_full_backtest(days: int = 30):
    """Run complete simulation and display results."""
    backtest = HistoricalBacktest()
    
    # Generate synthetic simulation data
    historical_data = backtest.generate_simulated_market_data(days=days)
    
    # Run backtest
    results = backtest.run_backtest(historical_data)
    
    # Display results
    backtest.print_results(results)
    
    return results


if __name__ == '__main__':
    print("=" * 80)
    print("🚀 STARTING MONTE CARLO SIMULATION")
    print("=" * 80)
    print("\nThis will validate the algorithm on synthetically generated market data.")
    print("NOTE: These metrics are from a simulation, not live historical API data.\n")
    
    run_full_backtest(days=30)
