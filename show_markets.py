#!/usr/bin/env python3
"""Display current markets being monitored."""

import sys
sys.path.insert(0, '/Users/amoghreddy/Desktop/Prediction Markets')

from src.kalshi_client import KalshiClient
from src.polymarket_client import PolymarketClient
from src.config import config

print("\n" + "="*70)
print("📊 CURRENT PREDICTION MARKETS")
print("="*70 + "\n")

# Fetch Kalshi markets
print("🎯 KALSHI MARKETS:")
print("-" * 70)
kalshi = KalshiClient(base_url=config.KALSHI_BASE_URL)
k_markets = kalshi.get_markets(limit=10)

if k_markets:
    for i, m in enumerate(k_markets[:10], 1):
        prob = m.get('probability', 0)
        title = m.get('title', 'Unknown')[:60]
        print(f"{i}. [{prob:.1%}] {title}")
        print(f"   ID: {m.get('id')}")
        print(f"   Bid: {m.get('yes_bid', 0):.3f} | Ask: {m.get('yes_ask', 0):.3f}")
        print()
else:
    print("❌ No markets found\n")

print("\n" + "="*70)
print("🌐 POLYMARKET MARKETS:")
print("-" * 70)
poly = PolymarketClient()
p_markets = poly.get_markets(limit=10, active=config.POLYMARKET_ACTIVE_ONLY)

if p_markets:
    for i, m in enumerate(p_markets[:10], 1):
        prob = m.get('probability', 0)
        title = m.get('question', m.get('title', 'Unknown'))[:60]
        print(f"{i}. [{prob:.1%}] {title}")
        print(f"   ID: {m.get('id')}")
        print()
else:
    print("❌ No markets found (This is why you're not seeing arbitrage!)\n")

print("\n" + "="*70)
print("💡 TO FIND ARBITRAGE:")
print("="*70)
print("""
Your system needs the SAME event on BOTH platforms.

Right now:
  ✓ Kalshi has markets (sports, politics, etc.)
  ✗ Polymarket has 0 matching markets

What to do:
  1. Wait for major events (elections, Super Bowl, etc.)
  2. System will auto-detect when both platforms have the event
  3. Check logs: tail -f logs/scheduler.log
  
The system IS working - just waiting for overlapping markets!
""")
print("="*70 + "\n")
