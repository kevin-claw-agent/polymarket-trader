"""
Web Dashboard Module
Real-time dashboard for monitoring the trading system
"""

from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import asyncio
import json
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global database reference (set by main.py)
db = None
config = {}


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })


@app.route('/api/markets')
def get_markets():
    """Get active markets"""
    async def fetch():
        if not db:
            return []
        return await db.get_latest_market_data()
    
    markets = asyncio.run(fetch())
    return jsonify({'markets': markets, 'count': len(markets)})


@app.route('/api/market/<market_id>')
def get_market_detail(market_id):
    """Get detailed market information"""
    async def fetch():
        if not db:
            return None
        
        # Get market data
        markets = await db.get_latest_market_data()
        market = next((m for m in markets if m['id'] == market_id), None)
        
        if not market:
            return None
        
        # Get price history
        history = await db.get_price_history(market_id, hours=24)
        
        # Get related signals
        # This would need a new query in database.py
        
        return {
            'market': market,
            'price_history': history
        }
    
    data = asyncio.run(fetch())
    if not data:
        return jsonify({'error': 'Market not found'}), 404
    
    return jsonify(data)


@app.route('/api/signals')
def get_signals():
    """Get trading signals"""
    async def fetch():
        if not db:
            return []
        
        # Get recent signals
        # This would need a query in database.py
        return []
    
    status_filter = request.args.get('status', 'all')
    signals = asyncio.run(fetch())
    
    if status_filter != 'all':
        signals = [s for s in signals if s.get('status') == status_filter]
    
    return jsonify({'signals': signals, 'count': len(signals)})


@app.route('/api/signals/pending')
def get_pending_signals():
    """Get signals awaiting approval"""
    return jsonify({'signals': [], 'count': 0})  # Placeholder


@app.route('/api/signals/<signal_id>/approve', methods=['POST'])
def approve_signal(signal_id):
    """Approve a trading signal"""
    async def approve():
        if not db:
            return False
        # Implementation would update signal status
        return True
    
    success = asyncio.run(approve())
    return jsonify({'success': success, 'signal_id': signal_id})


@app.route('/api/signals/<signal_id>/reject', methods=['POST'])
def reject_signal(signal_id):
    """Reject a trading signal"""
    data = request.json or {}
    reason = data.get('reason', 'Manual rejection')
    
    async def reject():
        if not db:
            return False
        # Implementation would update signal status
        return True
    
    success = asyncio.run(reject())
    return jsonify({'success': success, 'signal_id': signal_id, 'reason': reason})


@app.route('/api/anomalies')
def get_anomalies():
    """Get recent anomalies"""
    async def fetch():
        if not db:
            return []
        return await db.get_unprocessed_anomalies()
    
    anomalies = asyncio.run(fetch())
    return jsonify({'anomalies': anomalies, 'count': len(anomalies)})


@app.route('/api/performance')
def get_performance():
    """Get trading performance metrics"""
    async def fetch():
        if not db:
            return {}
        
        daily_pnl = await db.get_daily_pnl()
        weekly_pnl = await db.get_weekly_pnl()
        
        return {
            'daily_pnl': daily_pnl,
            'weekly_pnl': weekly_pnl,
            'open_positions': await db.get_open_positions_count(),
            'total_exposure': await db.get_total_exposure()
        }
    
    metrics = asyncio.run(fetch())
    return jsonify(metrics)


@app.route('/api/risk')
def get_risk_status():
    """Get risk management status"""
    return jsonify({
        'circuit_breaker': False,
        'daily_loss': 0,
        'exposure': 0,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/news')
def get_recent_news():
    """Get recent news"""
    return jsonify({'news': [], 'count': 0})  # Placeholder


# HTML Template (would normally be in templates/dashboard.html)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Trader Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #fff;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; }
        .status { display: flex; gap: 20px; }
        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 8px;
        }
        .status-label { font-size: 12px; opacity: 0.7; }
        .status-value { font-size: 18px; font-weight: bold; }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: #1a1f3a;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #2a3060;
        }
        .card h2 {
            font-size: 16px;
            margin-bottom: 15px;
            color: #8892b0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #2a3060;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #8892b0; }
        .metric-value { font-weight: bold; }
        .positive { color: #00d084; }
        .negative { color: #ff4757; }
        .neutral { color: #ffa502; }
        .signal-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .signal-item {
            background: #252b4d;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        .signal-item.buy { border-left-color: #00d084; }
        .signal-item.sell { border-left-color: #ff4757; }
        .signal-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .signal-action {
            font-weight: bold;
            text-transform: uppercase;
        }
        .signal-confidence {
            background: #667eea;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
        }
        .signal-market {
            font-size: 14px;
            color: #8892b0;
            margin-bottom: 10px;
        }
        .signal-details {
            display: flex;
            gap: 20px;
            font-size: 12px;
        }
        .signal-detail span { color: #8892b0; }
        .btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            margin-right: 5px;
        }
            margin-right: 5px;
        }
        .btn:hover { background: #5568d3; }
        .btn-success { background: #00d084; }
        .btn-danger { background: #ff4757; }
        .refresh-indicator {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #1a1f3a;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 12px;
        }
        .loading { animation: pulse 1.5s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #2a3060;
        }
        th {
            color: #8892b0;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Polymarket Trader</h1>
        <div class="status">
            <div class="status-item">
                <div class="status-label">Daily PnL</div>
                <div class="status-value positive" id="daily-pnl">+0.00%</div>
            </div>
            <div class="status-item">
                <div class="status-label">Open Positions</div>
                <div class="status-value" id="open-positions">0</div>
            </div>
            <div class="status-item">
                <div class="status-label">Exposure</div>
                <div class="status-value" id="exposure">0.0%</div>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="grid">
            <div class="card">
                <h2>📊 Performance</h2>
                <div class="metric">
                    <span class="metric-label">Daily PnL</span>
                    <span class="metric-value positive" id="perf-daily">+0.00%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Weekly PnL</span>
                    <span class="metric-value" id="perf-weekly">0.00%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Signals</span>
                    <span class="metric-value" id="perf-signals">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Win Rate</span>
                    <span class="metric-value" id="perf-winrate">0%</span>
                </div>
            </div>

            <div class="card">
                <h2>⚠️ Risk Status</h2>
                <div class="metric">
                    <span class="metric-label">Circuit Breaker</span>
                    <span class="metric-value" id="risk-circuit">Inactive</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Daily Loss</span>
                    <span class="metric-value" id="risk-daily-loss">0.00%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Exposure</span>
                    <span class="metric-value" id="risk-exposure">0.0%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Available Margin</span>
                    <span class="metric-value" id="risk-margin">100%</span>
                </div>
            </div>

            <div class="card">
                <h2>🔔 Recent Activity</h2>
                <div id="recent-activity">
                    <p style="color: #8892b0; text-align: center; padding: 20px;">
                        No recent activity
                    </p>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>🎯 Pending Signals</h2>
            <div class="signal-list" id="pending-signals">
                <p style="color: #8892b0; text-align: center; padding: 40px;">
                    No pending signals
                </p>
            </div>
        </div>

        <div class="card">
            <h2>📈 Active Markets</h2>
            <table>
                <thead>
                    <tr>
                        <th>Market</th>
                        <th>Category</th>
                        <th>Price</th>
                        <th>24h Volume</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="markets-table">
                </tbody>
            </table>
        </div>
    </div>

    <div class="refresh-indicator">
        Last updated: <span id="last-update">--:--:--</span>
        <span class="loading">⟳</span>
    </div>

    <script>
        // Dashboard JavaScript
        const REFRESH_INTERVAL = 5000; // 5 seconds

        async function fetchData() {
            try {
                // Fetch performance
                const perfResponse = await fetch('/api/performance');
                const perf = await perfResponse.json();
                updatePerformance(perf);

                // Fetch risk status
                const riskResponse = await fetch('/api/risk');
                const risk = await riskResponse.json();
                updateRisk(risk);

                // Update timestamp
                document.getElementById('last-update').textContent = 
                    new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        function updatePerformance(data) {
            const dailyEl = document.getElementById('perf-daily');
            const weeklyEl = document.getElementById('perf-weekly');
            
            dailyEl.textContent = (data.daily_pnl >= 0 ? '+' : '') + (data.daily_pnl * 100).toFixed(2) + '%';
            dailyEl.className = 'metric-value ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
            
            weeklyEl.textContent = (data.weekly_pnl >= 0 ? '+' : '') + (data.weekly_pnl * 100).toFixed(2) + '%';
            weeklyEl.className = 'metric-value ' + (data.weekly_pnl >= 0 ? 'positive' : 'negative');
            
            document.getElementById('daily-pnl').textContent = dailyEl.textContent;
            document.getElementById('daily-pnl').className = 'status-value ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
            document.getElementById('open-positions').textContent = data.open_positions || 0;
            document.getElementById('exposure').textContent = ((data.total_exposure || 0) * 100).toFixed(1) + '%';
        }

        function updateRisk(data) {
            document.getElementById('risk-circuit').textContent = data.circuit_breaker ? 'ACTIVE' : 'Inactive';
            document.getElementById('risk-circuit').className = 'metric-value ' + (data.circuit_breaker ? 'negative' : 'positive');
            document.getElementById('risk-exposure').textContent = ((data.exposure || 0) * 100).toFixed(1) + '%';
        }

        // Initial load
        fetchData();
        
        // Auto-refresh
        setInterval(fetchData, REFRESH_INTERVAL);
    </script>
</body>
</html>
'''


@app.route('/dashboard.html')
def dashboard_html():
    """Serve dashboard HTML"""
    return HTML_TEMPLATE


def init_dashboard(database, cfg: Dict):
    """Initialize dashboard with database connection"""
    global db, config
    db = database
    config = cfg
    
    dashboard_config = cfg.get('dashboard', {})
    host = dashboard_config.get('host', '0.0.0.0')
    port = dashboard_config.get('port', 8080)
    
    logger.info(f"Dashboard initialized on http://{host}:{port}")
    
    return host, port


if __name__ == '__main__':
    # Standalone run for development
    app.run(debug=True, host='0.0.0.0', port=8080)
