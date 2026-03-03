"""Email notification system for arbitrage opportunities."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
from loguru import logger

from .config import config


class EmailNotifier:
    """Send email alerts for arbitrage opportunities."""
    
    def __init__(self):
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
        self.email_from = config.EMAIL_FROM
        self.email_password = config.EMAIL_PASSWORD
        self.email_to = config.EMAIL_TO
        self.enabled = config.EMAIL_NOTIFICATIONS_ENABLED
        
    def send_arbitrage_alert(self, opportunity: Dict) -> bool:
        """
        Send email alert for new arbitrage opportunity.
        
        Args:
            opportunity: Dictionary containing opportunity details
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Email notifications disabled, skipping alert")
            return False
            
        if not all([self.smtp_server, self.email_from, self.email_password, self.email_to]):
            logger.warning("Email configuration incomplete, cannot send notification")
            return False
        
        try:
            # Create email content
            subject = f"🚨 ARBITRAGE ALERT: {opportunity.get('spread_percent', 0):.2f}% Spread"
            
            html_body = self._create_html_email(opportunity)
            text_body = self._create_text_email(opportunity)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            # Attach both plain text and HTML versions
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            logger.info(f"✓ Arbitrage alert sent to {self.email_to}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to send email notification: {e}")
            return False
    
    def _create_text_email(self, opp: Dict) -> str:
        """Create plain text email body."""
        return f"""
🚨 ARBITRAGE OPPORTUNITY DETECTED 🚨

Event: {opp.get('event_description', 'Unknown')}

📊 DETAILS:
-----------
Spread: {opp.get('spread_percent', 0):.2f}%
Expected ROI: {opp.get('expected_roi', 0):.2f}%
Confidence: {opp.get('confidence', 0):.1f}%

💰 KALSHI:
-----------
Probability: {opp.get('kalshi_probability', 0):.2f}%
Bid: ${opp.get('kalshi_bid', 0):.4f}
Ask: ${opp.get('kalshi_ask', 0):.4f}

💰 POLYMARKET:
-----------
Probability: {opp.get('polymarket_probability', 0):.2f}%
Bid: ${opp.get('polymarket_bid', 0):.4f}
Ask: ${opp.get('polymarket_ask', 0):.4f}

⚡ RECOMMENDED ACTION:
-----------
{opp.get('recommended_action', 'Review opportunity and execute if profitable')}

🕐 Detected: {opp.get('timestamp', datetime.utcnow())}

---
Prediction Market Arbitrage System
"""
    
    def _create_html_email(self, opp: Dict) -> str:
        """Create HTML email body."""
        spread = opp.get('spread_percent', 0)
        roi = opp.get('expected_roi', 0)
        
        # Color based on spread size
        color = '#00ff00' if spread > 10 else '#ffaa00' if spread > 5 else '#ff6600'
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
        .container {{ background-color: white; padding: 30px; border-radius: 10px; max-width: 600px; margin: 0 auto; }}
        .header {{ background-color: {color}; color: white; padding: 20px; border-radius: 5px; text-align: center; }}
        .metric {{ background-color: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid {color}; }}
        .platform {{ display: inline-block; width: 48%; vertical-align: top; }}
        .action {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin-top: 20px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
        h1 {{ margin: 0; }}
        h2 {{ color: #333; border-bottom: 2px solid {color}; padding-bottom: 10px; }}
        .value {{ font-size: 24px; font-weight: bold; color: {color}; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 ARBITRAGE OPPORTUNITY</h1>
        </div>
        
        <h2>📊 Opportunity Details</h2>
        <div class="metric">
            <strong>Event:</strong> {opp.get('event_description', 'Unknown')}
        </div>
        
        <div class="metric">
            <strong>Spread:</strong> <span class="value">{spread:.2f}%</span><br>
            <strong>Expected ROI:</strong> <span class="value">{roi:.2f}%</span><br>
            <strong>Confidence:</strong> {opp.get('confidence', 0):.1f}%
        </div>
        
        <h2>💰 Platform Comparison</h2>
        <div class="platform" style="margin-right: 4%;">
            <h3>Kalshi</h3>
            <strong>Probability:</strong> {opp.get('kalshi_probability', 0):.2f}%<br>
            <strong>Bid:</strong> ${opp.get('kalshi_bid', 0):.4f}<br>
            <strong>Ask:</strong> ${opp.get('kalshi_ask', 0):.4f}
        </div>
        
        <div class="platform">
            <h3>Polymarket</h3>
            <strong>Probability:</strong> {opp.get('polymarket_probability', 0):.2f}%<br>
            <strong>Bid:</strong> ${opp.get('polymarket_bid', 0):.4f}<br>
            <strong>Ask:</strong> ${opp.get('polymarket_ask', 0):.4f}
        </div>
        
        <div class="action">
            <strong>⚡ Recommended Action:</strong><br>
            {opp.get('recommended_action', 'Review opportunity and execute if profitable')}
        </div>
        
        <div class="footer">
            🕐 Detected: {opp.get('timestamp', datetime.utcnow())}<br>
            Prediction Market Arbitrage System
        </div>
    </div>
</body>
</html>
"""
    
    def send_daily_summary(self, opportunities: List[Dict], stats: Dict) -> bool:
        """
        Send daily summary email.
        
        Args:
            opportunities: List of opportunities detected today
            stats: Dictionary of daily statistics
            
        Returns:
            True if email sent successfully
        """
        if not self.enabled:
            return False
            
        try:
            subject = f"📊 Daily Summary: {len(opportunities)} Opportunities"
            
            text_body = f"""
DAILY ARBITRAGE SUMMARY
{datetime.utcnow().strftime('%Y-%m-%d')}

Total Opportunities: {len(opportunities)}
Total Spread: {stats.get('total_spread', 0):.2f}%
Average Spread: {stats.get('avg_spread', 0):.2f}%
Best Opportunity: {stats.get('best_spread', 0):.2f}%

Markets Monitored:
- Kalshi: {stats.get('kalshi_markets', 0)}
- Polymarket: {stats.get('polymarket_markets', 0)}

API Health: {stats.get('api_health', 'Unknown')}
"""
            
            msg = MIMEText(text_body)
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            logger.info("✓ Daily summary sent")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to send daily summary: {e}")
            return False
