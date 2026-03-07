#!/usr/bin/env python3
"""
Real backtest — replays actual price observations stored in your PostgreSQL/MySQL
database through the arbitrage detection algorithm.

Unlike backtest.py (which uses synthetically generated data), this module reads
the real `prices` table that the scheduler has been writing to, and applies the
exact same Bayesian smoothing + spread detection logic used in production.

USAGE
-----
    python real_backtest.py                  # all data in DB
    python real_backtest.py --days 7         # last 7 days only
    python real_backtest.py --min-obs 20     # only contracts with ≥20 observations

REQUIREMENTS
------------
The scheduler must have been running long enough to accumulate meaningful price
history. As a rule of thumb you need at least 50 observations per contract pair
(≈50 minutes at 60s polling) to get useful Bayesian warm-up + spread statistics.

Run `python real_backtest.py --status` to check how much data you have before
running the full backtest.
"""

import sys
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

sys.path.insert(0, '.')

from src.config import config
from src.database import get_db_session
from src.models import Price, MatchedContract
from src.bayesian import BayesianEngine


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_data_status() -> None:
    """Print a summary of what real data is available in the database."""
    print("\n" + "=" * 70)
    print("📊 REAL DATA STATUS")
    print("=" * 70)

    with get_db_session() as session:
        # Per-contract observation counts
        contracts = session.query(MatchedContract).filter_by(active=True).all()

        if not contracts:
            print("\n⚠️  No active matched contracts found.")
            print("   Start the scheduler: python -m src.scheduler")
            return

        print(f"\n{'Contract':<50} {'Obs':>5} {'Platforms':>10} {'Date range'}")
        print("-" * 90)

        total_obs = 0
        usable = 0
        for mc in contracts:
            prices = (
                session.query(Price)
                .filter_by(contract_id=mc.id)
                .order_by(Price.timestamp)
                .all()
            )
            n = len(prices)
            total_obs += n
            platforms = {p.platform for p in prices}
            if prices:
                span = f"{prices[0].timestamp.strftime('%m-%d')} → {prices[-1].timestamp.strftime('%m-%d')}"
            else:
                span = "—"

            has_both = len(platforms) == 2
            flag = "✅" if (n >= 20 and has_both) else "⚠️ "
            if n >= 20 and has_both:
                usable += 1

            title = mc.event_title[:48]
            plat_str = "+".join(sorted(platforms)) if platforms else "none"
            print(f"{flag} {title:<48} {n:>5} {plat_str:>10}  {span}")

        print("-" * 90)
        print(f"\nTotal price observations : {total_obs:,}")
        print(f"Contracts with ≥20 obs   : {usable} / {len(contracts)}")

        if usable == 0:
            print("\n⚠️  Not enough data for a meaningful backtest yet.")
            print("   Keep the scheduler running — you need at least a few hours of")
            print("   continuous data per contract before results are useful.")
        else:
            print(f"\n✅ Ready to backtest {usable} contract(s).")
            print("   Run: python real_backtest.py")


# ── Core backtest ─────────────────────────────────────────────────────────────

def load_price_series(
    days: Optional[int],
    min_obs: int,
) -> Dict[int, Dict]:
    """
    Load price history from the database grouped by contract.

    Returns a dict keyed by contract_id:
      {
        'contract': MatchedContract ORM object,
        'series': [{'timestamp', 'kalshi_prob', 'polymarket_prob'}, ...]
      }
    Only contracts that have observations from BOTH platforms and at least
    `min_obs` total rows are included.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=days)
        if days else None
    )

    result = {}

    with get_db_session() as session:
        contracts = session.query(MatchedContract).filter_by(active=True).all()

        for mc in contracts:
            query = session.query(Price).filter_by(contract_id=mc.id)
            if cutoff:
                query = query.filter(Price.timestamp >= cutoff)
            prices = query.order_by(Price.timestamp).all()

            if len(prices) < min_obs:
                continue

            # Build per-timestamp lookup for each platform
            kalshi_map: Dict[datetime, float] = {}
            poly_map:   Dict[datetime, float] = {}

            for p in prices:
                ts = p.timestamp
                prob = float(p.probability)
                if p.platform == 'kalshi':
                    kalshi_map[ts] = prob
                else:
                    poly_map[ts] = prob

            if not kalshi_map or not poly_map:
                continue   # need both platforms

            # Align: for every kalshi timestamp find the nearest polymarket
            # price within a 90-second window (one poll cycle tolerance).
            aligned = []
            poly_times = sorted(poly_map.keys())

            for k_ts, k_prob in sorted(kalshi_map.items()):
                # Binary search for closest polymarket timestamp
                lo, hi = 0, len(poly_times) - 1
                best: Optional[datetime] = None
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if poly_times[mid] <= k_ts:
                        best = poly_times[mid]
                        lo = mid + 1
                    else:
                        hi = mid - 1

                if best is None and poly_times:
                    best = poly_times[0]

                if best is not None:
                    gap = abs((k_ts - best).total_seconds())
                    if gap <= 90:
                        aligned.append({
                            'timestamp':      k_ts,
                            'kalshi_prob':    k_prob,
                            'polymarket_prob': poly_map[best],
                        })

            if len(aligned) < min_obs // 2:
                continue

            # Detach ORM object so it survives outside the session
            session.expunge(mc)
            result[mc.id] = {
                'contract': mc,
                'series':   aligned,
            }

    return result


def run_real_backtest(days: Optional[int] = None, min_obs: int = 20) -> Dict:
    """
    Replay real price observations through the detection algorithm.

    Detection logic is identical to the live scheduler:
      1. Beta-Binomial Bayesian smoothing per (contract, platform)
      2. Fee-adjusted net spread on smoothed probabilities
      3. Open an opportunity window when net_spread > MIN_SPREAD_THRESHOLD
      4. Close it when net_spread falls below threshold (or data ends)
      5. One opportunity record per contiguous open window

    Returns a results dict suitable for print_results().
    """
    print("\n" + "=" * 70)
    print("🔁 REAL BACKTEST — replaying live price observations")
    print("=" * 70)

    data = load_price_series(days=days, min_obs=min_obs)

    if not data:
        print("\n⚠️  No usable contracts found (need both platforms + "
              f"≥{min_obs} observations).")
        print("   Run: python real_backtest.py --status")
        return {}

    print(f"\n📦 Loaded {len(data)} contract(s) with sufficient history")
    if days:
        print(f"   Time window : last {days} day(s)")
    print(f"   Min obs     : {min_obs}")
    print(f"   Fee Kalshi  : {config.FEE_KALSHI*100:.1f}%")
    print(f"   Fee Poly    : {config.FEE_POLYMARKET*100:.1f}%")
    print(f"   Threshold   : {config.MIN_SPREAD_THRESHOLD*100:.2f}% net spread\n")

    bayesian = BayesianEngine()
    window_size = bayesian.window_size

    # Per-contract in-memory Bayesian state (avoids DB writes during replay)
    bayes_state: Dict[str, Dict] = {}

    def bayesian_update(key: str, p: float) -> float:
        """In-memory Beta-Binomial conjugate update; returns posterior mean."""
        if key not in bayes_state:
            bayes_state[key] = {'alpha': 1.0, 'beta': 1.0, 'n': 0}
        s = bayes_state[key]
        if s['n'] >= window_size:
            scale = (window_size - 1) / window_size
            s['alpha'] *= scale
            s['beta']  *= scale
        s['alpha'] += p
        s['beta']  += (1.0 - p)
        s['n']     += 1
        return s['alpha'] / (s['alpha'] + s['beta'])

    opportunities = []
    all_spreads   = []
    contract_summaries = []

    for contract_id, entry in data.items():
        mc     = entry['contract']
        series = entry['series']

        k_key = f"kalshi_{contract_id}"
        p_key = f"poly_{contract_id}"

        open_time   = None
        open_k_prob = None
        open_p_prob = None
        peak_spread = 0.0
        peak_raw    = 0.0
        contract_opps = 0

        for obs in series:
            smoothed_k = bayesian_update(k_key, obs['kalshi_prob'])
            smoothed_p = bayesian_update(p_key, obs['polymarket_prob'])

            raw_spread = abs(obs['kalshi_prob'] - obs['polymarket_prob'])
            net_spread = (
                abs(smoothed_k - smoothed_p)
                - (config.FEE_KALSHI + config.FEE_POLYMARKET)
            )
            all_spreads.append(raw_spread)

            above = net_spread > config.MIN_SPREAD_THRESHOLD

            if above and open_time is None:
                open_time   = obs['timestamp']
                open_k_prob = obs['kalshi_prob']
                open_p_prob = obs['polymarket_prob']
                peak_spread = net_spread
                peak_raw    = raw_spread

            elif above and open_time is not None:
                peak_spread = max(peak_spread, net_spread)
                peak_raw    = max(peak_raw,    raw_spread)

            elif not above and open_time is not None:
                duration_s = (obs['timestamp'] - open_time).total_seconds()
                opportunities.append({
                    'contract_id':    contract_id,
                    'event_title':    mc.event_title,
                    'kalshi_id':      mc.kalshi_id,
                    'open_time':      open_time,
                    'close_time':     obs['timestamp'],
                    'duration_min':   duration_s / 60,
                    'kalshi_prob':    open_k_prob,
                    'polymarket_prob': open_p_prob,
                    'peak_net_spread': peak_spread,
                    'peak_raw_spread': peak_raw,
                    'profit_pct':     peak_spread * 100,
                })
                contract_opps += 1
                open_time = None

        # Close any window still open at end of data
        if open_time is not None:
            last = series[-1]
            duration_s = (last['timestamp'] - open_time).total_seconds()
            opportunities.append({
                'contract_id':    contract_id,
                'event_title':    mc.event_title,
                'kalshi_id':      mc.kalshi_id,
                'open_time':      open_time,
                'close_time':     last['timestamp'],
                'duration_min':   duration_s / 60,
                'kalshi_prob':    open_k_prob,
                'polymarket_prob': open_p_prob,
                'peak_net_spread': peak_spread,
                'peak_raw_spread': peak_raw,
                'profit_pct':     peak_spread * 100,
            })
            contract_opps += 1

        contract_summaries.append({
            'title':       mc.event_title[:60],
            'kalshi_id':   mc.kalshi_id,
            'obs':         len(series),
            'opps':        contract_opps,
        })

    # ── Sharpe (annualised daily P&L) ────────────────────────────────────────
    sharpe = 0.0
    if len(opportunities) >= 2:
        daily_pnl: Dict[str, float] = {}
        for opp in opportunities:
            ts = opp['open_time']
            day_key = ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts)[:10]
            daily_pnl[day_key] = daily_pnl.get(day_key, 0.0) + opp['peak_net_spread']

        # All days covered by the data
        all_day_keys: set = set()
        for entry in data.values():
            for obs in entry['series']:
                ts = obs['timestamp']
                all_day_keys.add(ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts)[:10])

        pnl_series = np.array([daily_pnl.get(d, 0.0) for d in all_day_keys])
        mean_d = pnl_series.mean()
        std_d  = pnl_series.std(ddof=1)
        if std_d > 0:
            sharpe = round(float(mean_d / std_d * np.sqrt(252)), 2)

    # ── Total observations across all contracts ───────────────────────────────
    total_obs = sum(len(e['series']) for e in data.values())

    # ── Date range of data ────────────────────────────────────────────────────
    all_timestamps = [
        obs['timestamp']
        for entry in data.values()
        for obs in entry['series']
    ]
    date_min = min(all_timestamps) if all_timestamps else None
    date_max = max(all_timestamps) if all_timestamps else None

    results = {
        'contracts_analyzed':   len(data),
        'total_observations':   total_obs,
        'date_min':             date_min,
        'date_max':             date_max,
        'opportunities_found':  len(opportunities),
        'avg_raw_spread':       float(np.mean(all_spreads)) if all_spreads else 0.0,
        'avg_net_spread_pct':   float(np.mean([o['profit_pct'] for o in opportunities])) if opportunities else 0.0,
        'avg_duration_min':     float(np.mean([o['duration_min'] for o in opportunities])) if opportunities else 0.0,
        'sharpe_ratio':         sharpe,
        'opportunities':        opportunities,
        'contract_summaries':   contract_summaries,
    }
    return results


def print_results(results: Dict) -> None:
    """Print the real backtest results."""
    if not results:
        return

    opps = results['opportunities']
    d_min = results['date_min']
    d_max = results['date_max']
    span  = (
        f"{d_min.strftime('%Y-%m-%d')} → {d_max.strftime('%Y-%m-%d')}"
        if d_min and d_max else "unknown"
    )

    print("\n" + "=" * 70)
    print("✅ REAL BACKTEST RESULTS  (live price observations from DB)")
    print("=" * 70)

    print(f"\n🔍 DATA")
    print(f"  Contracts analysed  : {results['contracts_analyzed']}")
    print(f"  Price observations  : {results['total_observations']:,}")
    print(f"  Date range          : {span}")

    print(f"\n💰 DETECTIONS")
    print(f"  Arbitrage windows   : {results['opportunities_found']}")
    print(f"  Avg raw spread      : {results['avg_raw_spread']*100:.2f}%")
    print(f"  Avg net spread      : {results['avg_net_spread_pct']:.2f}%")
    print(f"  Avg duration        : {results['avg_duration_min']:.1f} min")
    if results['opportunities_found'] >= 2:
        print(f"  Sharpe (annualised) : {results['sharpe_ratio']:.2f}")

    print(f"\n📋 PER-CONTRACT SUMMARY")
    print(f"  {'Contract':<60} {'Obs':>5} {'Opps':>5}")
    print("  " + "-" * 74)
    for s in results['contract_summaries']:
        print(f"  {s['title']:<60} {s['obs']:>5} {s['opps']:>5}")

    if opps:
        print(f"\n🎯 TOP 5 OPPORTUNITIES (by peak net spread)")
        print("  " + "-" * 74)
        top5 = sorted(opps, key=lambda x: x['peak_net_spread'], reverse=True)[:5]
        for i, opp in enumerate(top5, 1):
            ot = opp['open_time']
            ts = ot.strftime('%Y-%m-%d %H:%M') if hasattr(ot, 'strftime') else str(ot)[:16]
            print(f"\n  {i}. {ts}  (duration: {opp['duration_min']:.0f} min)")
            print(f"     {opp['event_title'][:65]}")
            print(f"     Peak net spread : {opp['peak_net_spread']*100:.2f}%  |  "
                  f"Raw spread : {opp['peak_raw_spread']*100:.2f}%")
            print(f"     Kalshi: {opp['kalshi_prob']:.3f}  |  "
                  f"Polymarket: {opp['polymarket_prob']:.3f}")

    print(f"\n{'='*70}")

    if results['opportunities_found'] == 0:
        print("\n💡 No arbitrage windows detected yet.")
        print("   This could mean:")
        print("   • Not enough price history (run scheduler longer)")
        print("   • MIN_SPREAD_THRESHOLD is above the actual spreads in your data")
        print(f"   • Current threshold: {config.MIN_SPREAD_THRESHOLD*100:.2f}%  "
              f"(fees: {(config.FEE_KALSHI+config.FEE_POLYMARKET)*100:.0f}%)")
        if results['avg_raw_spread'] > 0:
            print(f"   • Avg raw spread in data: {results['avg_raw_spread']*100:.2f}% — "
                  f"{'above' if results['avg_raw_spread'] > config.MIN_SPREAD_THRESHOLD + config.FEE_KALSHI + config.FEE_POLYMARKET else 'below'} the profitable threshold")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Real backtest: replay live DB price observations through '
                    'the arbitrage detection algorithm.'
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Show how much real data is available without running the backtest'
    )
    parser.add_argument(
        '--days', type=int, default=None,
        help='Only use data from the last N days (default: all data)'
    )
    parser.add_argument(
        '--min-obs', type=int, default=20,
        help='Minimum observations per contract to include (default: 20)'
    )
    args = parser.parse_args()

    if args.status:
        check_data_status()
        return

    results = run_real_backtest(days=args.days, min_obs=args.min_obs)
    print_results(results)


if __name__ == '__main__':
    main()
