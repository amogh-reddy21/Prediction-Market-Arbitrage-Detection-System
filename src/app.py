"""Flask REST API for arbitrage dashboard."""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import joinedload

from .config import config
from .database import get_db_session
from .models import Opportunity, MatchedContract, Price, APIHealth
from .matcher import ContractMatcher
from .tracker import OpportunityTracker

app = Flask(__name__)
CORS(app)

# Initialize components
matcher = ContractMatcher()
tracker = OpportunityTracker()

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check endpoint."""
    with get_db_session() as session:
        api_health = session.query(APIHealth).all()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'platforms': [
                {
                    'platform': h.platform,
                    'status': h.status,
                    'last_successful_call': h.last_successful_call.isoformat() if h.last_successful_call else None,
                    'consecutive_failures': h.consecutive_failures
                }
                for h in api_health
            ]
        })

@app.route('/api/live', methods=['GET'])
def get_live_opportunities():
    """Get currently open arbitrage opportunities."""
    with get_db_session() as session:
        open_opps = (
            session.query(Opportunity)
            .options(joinedload(Opportunity.contract))
            .filter_by(status='open')
            .order_by(Opportunity.fee_adjusted_spread.desc())
            .all()
        )
        
        results = []
        for opp in open_opps:
            contract = opp.contract
            
            duration_seconds = (datetime.now(timezone.utc) - opp.open_time).total_seconds()
            
            results.append({
                'id': opp.id,
                'contract_id': opp.contract_id,
                'event_title': contract.event_title,
                'kalshi_id': contract.kalshi_id,
                'polymarket_id': contract.polymarket_id,
                'raw_spread': float(opp.raw_spread),
                'fee_adjusted_spread': float(opp.fee_adjusted_spread),
                'kalshi_prob': float(opp.kalshi_prob_open),
                'polymarket_prob': float(opp.polymarket_prob_open),
                'peak_spread': float(opp.peak_spread),
                'open_time': opp.open_time.isoformat(),
                'duration_seconds': duration_seconds,
                'decay_observations': opp.decay_observations
            })
        
        return jsonify({
            'opportunities': results,
            'count': len(results),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

@app.route('/api/history', methods=['GET'])
def get_opportunity_history():
    """Get historical closed opportunities."""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    with get_db_session() as session:
        closed_opps = (
            session.query(Opportunity)
            .options(joinedload(Opportunity.contract))
            .filter_by(status='closed')
            .order_by(Opportunity.close_time.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        
        results = []
        for opp in closed_opps:
            contract = opp.contract
            
            if opp.close_time:
                duration_seconds = (opp.close_time - opp.open_time).total_seconds()
            else:
                duration_seconds = None
            
            results.append({
                'id': opp.id,
                'contract_id': opp.contract_id,
                'event_title': contract.event_title,
                'raw_spread': float(opp.raw_spread),
                'fee_adjusted_spread': float(opp.fee_adjusted_spread),
                'peak_spread': float(opp.peak_spread),
                'kalshi_prob_open': float(opp.kalshi_prob_open),
                'polymarket_prob_open': float(opp.polymarket_prob_open),
                'kalshi_prob_close': float(opp.kalshi_prob_close) if opp.kalshi_prob_close else None,
                'polymarket_prob_close': float(opp.polymarket_prob_close) if opp.polymarket_prob_close else None,
                'open_time': opp.open_time.isoformat(),
                'close_time': opp.close_time.isoformat() if opp.close_time else None,
                'duration_seconds': duration_seconds,
                'decay_observations': opp.decay_observations
            })
        
        return jsonify({
            'opportunities': results,
            'count': len(results),
            'offset': offset,
            'limit': limit
        })

@app.route('/api/stats', methods=['GET'])
@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get overall system statistics."""
    stats = tracker.get_statistics()
    
    return jsonify({
        'total_opportunities': stats['total_opportunities'],
        'open_opportunities': stats['open_opportunities'],
        'closed_opportunities': stats['closed_opportunities'],
        'average_duration_seconds': stats['average_duration_seconds'],
        'average_peak_spread': stats['average_peak_spread'],
        'edge_half_life_seconds': stats['edge_half_life'],
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/contracts', methods=['GET'])
def get_matched_contracts():
    """Get all matched contract pairs."""
    active_only = request.args.get('active', 'true').lower() == 'true'
    
    with get_db_session() as session:
        query = session.query(MatchedContract)
        
        if active_only:
            query = query.filter_by(active=True)
        
        contracts = query.order_by(MatchedContract.match_score.desc()).all()
        
        results = []
        for contract in contracts:
            results.append({
                'id': contract.id,
                'kalshi_id': contract.kalshi_id,
                'polymarket_id': contract.polymarket_id,
                'event_title': contract.event_title,
                'match_score': contract.match_score,
                'verified': contract.verified,
                'active': contract.active,
                'created_at': contract.created_at.isoformat()
            })
        
        return jsonify({
            'contracts': results,
            'count': len(results)
        })

@app.route('/api/decay/<int:opportunity_id>', methods=['GET'])
def get_decay_curve(opportunity_id):
    """Get decay curve for a specific opportunity."""
    decay_data = tracker.get_decay_curve(opportunity_id)
    
    if not decay_data:
        return jsonify({'error': 'Opportunity not found'}), 404
    
    return jsonify({
        'opportunity_id': opportunity_id,
        'decay_curve': [
            {
                'timestamp': point['timestamp'].isoformat(),
                'spread': point['spread']
            }
            for point in decay_data
        ]
    })

@app.route('/api/contract/<int:contract_id>/prices', methods=['GET'])
def get_contract_prices(contract_id):
    """Get recent price history for a contract."""
    limit = request.args.get('limit', 100, type=int)
    
    with get_db_session() as session:
        prices = session.query(Price).filter_by(contract_id=contract_id).order_by(
            Price.timestamp.desc()
        ).limit(limit).all()
        
        results = []
        for price in prices:
            results.append({
                'platform': price.platform,
                'probability': float(price.probability),
                'bid_price': float(price.bid_price) if price.bid_price else None,
                'ask_price': float(price.ask_price) if price.ask_price else None,
                'volume_24h': float(price.volume_24h) if price.volume_24h else None,
                'timestamp': price.timestamp.isoformat()
            })
        
        return jsonify({
            'contract_id': contract_id,
            'prices': results,
            'count': len(results)
        })

@app.route('/api/contract/<int:contract_id>/verify', methods=['POST'])
def verify_contract(contract_id):
    """Manually verify a matched contract."""
    data = request.json
    verified = data.get('verified', True)
    
    matcher.manual_verify(contract_id, verified)
    
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'verified': verified
    })

@app.route('/api/contract/<int:contract_id>/deactivate', methods=['POST'])
def deactivate_contract(contract_id):
    """Deactivate a matched contract."""
    matcher.deactivate_match(contract_id)
    
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'active': False
    })

def main():
    """Run the Flask app."""
    logger.info(f"Starting Flask API server on {config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )

if __name__ == '__main__':
    main()
