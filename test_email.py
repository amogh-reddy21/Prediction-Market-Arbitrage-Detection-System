#!/usr/bin/env python3
"""Test email notification system."""

import sys
sys.path.insert(0, '/Users/amoghreddy/Desktop/Prediction Markets')

from src.notifier import EmailNotifier
from src.config import config
from datetime import datetime

print("\n" + "="*70)
print("📧 EMAIL NOTIFICATION TEST")
print("="*70 + "\n")

# Check configuration
print("📋 Configuration:")
print(f"   Enabled: {config.EMAIL_NOTIFICATIONS_ENABLED}")
print(f"   From: {config.EMAIL_FROM}")
print(f"   To: {config.EMAIL_TO}")
print(f"   SMTP: {config.SMTP_SERVER}:{config.SMTP_PORT}")
print(f"   Password set: {'Yes' if config.EMAIL_PASSWORD else 'No'}")
print()

if not config.EMAIL_NOTIFICATIONS_ENABLED:
    print("❌ Email notifications are DISABLED in .env")
    print("   Set EMAIL_NOTIFICATIONS_ENABLED=True")
    sys.exit(1)

if not config.EMAIL_PASSWORD or config.EMAIL_PASSWORD == 'your_app_password_here':
    print("❌ Email password not configured!")
    print()
    print("📝 Setup instructions:")
    print("   1. Go to: https://myaccount.google.com/apppasswords")
    print("   2. Create an app password for 'Mail'")
    print("   3. Copy the 16-character password")
    print("   4. Edit .env and set: EMAIL_PASSWORD=<your-app-password>")
    print("   5. Run this test again")
    sys.exit(1)

# Create test opportunity
test_opportunity = {
    'event_description': 'TEST: Will Bitcoin reach $100,000 by end of 2026?',
    'spread_percent': 8.5,
    'expected_roi': 7.2,
    'confidence': 85.0,
    'kalshi_probability': 45.0,
    'kalshi_bid': 0.42,
    'kalshi_ask': 0.48,
    'polymarket_probability': 53.5,
    'polymarket_bid': 0.51,
    'polymarket_ask': 0.56,
    'recommended_action': 'Buy on Kalshi at $0.48, sell on Polymarket at $0.51 for 7.2% profit',
    'timestamp': datetime.utcnow()
}

print("🚀 Sending test email...")
print()

notifier = EmailNotifier()

try:
    success = notifier.send_arbitrage_alert(test_opportunity)
    
    if success:
        print("✅ SUCCESS! Test email sent!")
        print()
        print(f"📬 Check your inbox: {config.EMAIL_TO}")
        print("   Subject: 🚨 ARBITRAGE ALERT: 8.50% Spread")
        print()
        print("💡 If you don't see it:")
        print("   - Check your spam folder")
        print("   - Wait 1-2 minutes for delivery")
        print("   - Verify EMAIL_TO address in .env")
    else:
        print("❌ Email failed to send")
        print("   Check logs/scheduler.log for errors")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    print()
    print("🔧 Common issues:")
    print("   - Wrong app password")
    print("   - 2-factor authentication not enabled on Gmail")
    print("   - SMTP server blocked by firewall")

print()
print("="*70)
