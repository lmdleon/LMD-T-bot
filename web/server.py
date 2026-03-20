#!/usr/bin/env python3
"""
Flask server for serving trades data from SQLite database.
Run this file to start the web interface: `python web/server.py`
"""

import os
import sys
from datetime import datetime
from flask import Flask, jsonify, send_from_directory

# Add app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.stats.sqlite_client import StatsSQLiteClient


app = Flask(__name__, static_folder='.', static_url_path='')

# Database path - adjust if your database is in a different location
DB_PATH = 'stats.db'


def get_db_client():
    """Get database client instance."""
    return StatsSQLiteClient(DB_PATH)


@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory('.', 'index.html')


@app.route('/api/trades')
def api_trades():
    """API endpoint to get all trades from database."""
    try:
        db = get_db_client()
        orders = db.get_orders()
        
        # Convert orders to list of dicts
        trades = []
        for order in orders:
            trade = {
                'id': order[0],
                'figi': order[1],
                'direction': order[2],
                'price': order[3],
                'quantity': order[4],
                'status': order[5],
                'order_datetime': order[6],
                'instrument_name': order[7],
                'average_position_price': order[8],
                'executed_commission': order[9],
                'initial_commission': order[10],
                'executed_order_price': order[11],
                'total_order_amount': order[12]
            }
            trades.append(trade)
        
        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/stats')
def api_stats():
    """API endpoint to get trade statistics."""
    try:
        db = get_db_client()
        orders = db.get_orders()
        
        if not orders:
            return jsonify({
                'success': True,
                'stats': {
                    'total': 0,
                    'filled': 0,
                    'cancelled': 0,
                    'rejected': 0,
                    'total_volume': 0,
                    'total_commission': 0
                },
                'timestamp': datetime.now().isoformat()
            })
        
        # Calculate statistics
        total = len(orders)
        filled = sum(1 for o in orders if o[5] == 'fill')
        cancelled = sum(1 for o in orders if o[5] == 'cancelled')
        rejected = sum(1 for o in orders if o[5] == 'rejected')
        
        total_volume = sum(o[4] * o[3] for o in orders if o[3])  # quantity * price
        total_commission = sum(o[9] or 0 for o in orders)  # executed_commission
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'filled': filled,
                'cancelled': cancelled,
                'rejected': rejected,
                'total_volume': round(total_volume, 2),
                'total_commission': round(total_commission, 2)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/stats/daily')
def api_stats_daily():
    """API endpoint to get daily trade statistics by asset."""
    try:
        db = get_db_client()
        orders = db.get_orders()
        
        if not orders:
            return jsonify({
                'success': True,
                'daily_stats': [],
                'total_summary': {
                    'total_trades': 0,
                    'total_commissions': 0,
                    'total_amounts': 0,
                    'total_result': 0
                },
                'timestamp': datetime.now().isoformat()
            })
        
        # Group orders by date and instrument
        daily_stats = {}
        
        for order in orders:
            order_id, figi, direction, price, quantity, status, order_datetime, instrument_name, average_position_price, executed_commission, initial_commission, executed_order_price, total_order_amount = order
            
            # Extract date from datetime string
            if order_datetime:
                date_str = order_datetime.split('T')[0]  # Get YYYY-MM-DD part
            else:
                continue
            
            # Calculate amount: buy = -price*quantity, sell = +price*quantity
            amount = total_order_amount
            if direction == '1':  # Buy
                amount = -amount
            
            key = (date_str, figi)
            
            if key not in daily_stats:
                daily_stats[key] = {
                    'date': date_str,
                    'figi': figi,
                    'instrument_name': instrument_name or figi,
                    'trade_count': 0,
                    'total_commissions': 0,
                    'total_amounts': 0
                }
            
            daily_stats[key]['trade_count'] += 1
            daily_stats[key]['total_commissions'] += (initial_commission or 0)
            daily_stats[key]['total_amounts'] += amount
        
        # Filter daily_stats: remove items with odd trade_count
        keys_to_remove = [key for key, stat in daily_stats.items() if stat['trade_count'] % 2 != 0]
        for key in keys_to_remove:
            del daily_stats[key]
        
        # Convert to list and calculate result
        stats_list = []
        for key, stat in daily_stats.items():
            stat['result'] = stat['total_amounts'] - stat['total_commissions']
            stats_list.append(stat)
        
        # Sort by date descending
        stats_list.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate total summary
        total_summary = {
            'total_trades': sum(s['trade_count'] for s in stats_list),
            'total_commissions': round(sum(s['total_commissions'] for s in stats_list), 2),
            'total_amounts': round(sum(s['total_amounts'] for s in stats_list), 2),
            'total_result': round(sum(s['result'] for s in stats_list), 2)
        }
        
        return jsonify({
            'success': True,
            'daily_stats': stats_list,
            'total_summary': total_summary,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LMD-T-bot Web Interface')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting LMD-T-bot Web Interface...")
    print(f"Database: {DB_PATH}")
    print(f"Server: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
