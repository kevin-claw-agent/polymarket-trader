"""
Backtest Visualizer Module
Creates visualizations of backtest results
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BacktestVisualizer:
    """Generates visualizations for backtest results"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.output_dir = self.config.get('output_dir', 'backtest_results')
    
    def generate_html_report(
        self,
        result: Any,
        strategy_name: str = "PriceOnlyStrategy",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Generate interactive HTML report with charts
        
        Returns:
            HTML string
        """
        data = result.to_dict()
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Backtest Report - {strategy_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #e0e6ed;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 2px solid #1e3a5f;
            margin-bottom: 40px;
        }}
        
        h1 {{
            font-size: 2.5em;
            color: #4fc3f7;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            color: #90a4ae;
            font-size: 1.1em;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            border: 1px solid #2a5585;
            transition: transform 0.2s;
        }}
        
        .metric-card:hover {{
            transform: translateY(-4px);
        }}
        
        .metric-label {{
            font-size: 0.85em;
            color: #90a4ae;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #4fc3f7;
        }}
        
        .metric-value.positive {{
            color: #4caf50;
        }}
        
        .metric-value.negative {{
            color: #f44336;
        }}
        
        .chart-container {{
            background: #0d2137;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 30px;
            border: 1px solid #1e3a5f;
        }}
        
        .chart-title {{
            font-size: 1.3em;
            color: #4fc3f7;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #1e3a5f;
        }}
        
        .chart-wrapper {{
            position: relative;
            height: 400px;
        }}
        
        .trades-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        .trades-table th,
        .trades-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #1e3a5f;
        }}
        
        .trades-table th {{
            background: #1e3a5f;
            color: #4fc3f7;
            font-weight: 600;
        }}
        
        .trades-table tr:hover {{
            background: #1a2d4a;
        }}
        
        .trades-table .positive {{
            color: #4caf50;
        }}
        
        .trades-table .negative {{
            color: #f44336;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section-title {{
            font-size: 1.5em;
            color: #4fc3f7;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #1e3a5f;
        }}
        
        .signal-type-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }}
        
        .signal-type-card {{
            background: #0d2137;
            border-radius: 8px;
            padding: 16px;
            border-left: 4px solid #4fc3f7;
        }}
        
        .signal-type-card h4 {{
            color: #4fc3f7;
            margin-bottom: 10px;
        }}
        
        .signal-type-card .stats {{
            display: flex;
            justify-content: space-between;
            font-size: 0.9em;
            color: #90a4ae;
        }}
        
        footer {{
            text-align: center;
            padding: 40px 0;
            color: #90a4ae;
            border-top: 2px solid #1e3a5f;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 Polymarket Backtest Report</h1>
            <p class="subtitle">Strategy: {strategy_name} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
        </header>
        
        <div class="summary-grid">
            <div class="metric-card">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{data['summary']['total_trades']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value {'positive' if data['summary']['win_rate'] >= 0.5 else 'negative'}">{data['summary']['win_rate']:.1%}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Return</div>
                <div class="metric-value {'positive' if data['summary']['total_return_percent'] >= 0 else 'negative'}">{data['summary']['total_return_percent']:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value negative">{data['summary']['max_drawdown_percent']:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value {'positive' if data['summary']['sharpe_ratio'] >= 1 else ''}">{data['summary']['sharpe_ratio']:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value {'positive' if data['summary']['profit_factor'] >= 1.5 else ''}">{data['summary']['profit_factor']:.2f}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">📈 Equity Curve</div>
            <div class="chart-wrapper">
                <canvas id="equityChart"></canvas>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">📊 Trade Distribution</div>
            <div class="chart-wrapper">
                <canvas id="tradeChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📋 Trade History</h2>
            <div style="overflow-x: auto;">
                <table class="trades-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Time</th>
                            <th>Signal Type</th>
                            <th>Action</th>
                            <th>Entry</th>
                            <th>Exit</th>
                            <th>Confidence</th>
                            <th>P&L ($)</th>
                            <th>P&L (%)</th>
                            <th>Exit Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_trades_rows(data['trades'][:50])}
                    </tbody>
                </table>
                {f"<p style='text-align: center; color: #90a4ae; margin-top: 10px;'>Showing first 50 of {len(data['trades'])} trades</p>" if len(data['trades']) > 50 else ''}
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">🎯 Signal Type Performance</h2>
            <div class="signal-type-grid">
                {self._generate_signal_type_cards(data['trades'])}
            </div>
        </div>
        
        <footer>
            <p>Polymarket Trader Backtest Engine v1.0</p>
            <p style="font-size: 0.9em; margin-top: 10px;">This report is for informational purposes only. Past performance does not guarantee future results.</p>
        </footer>
    </div>
    
    <script>
        // Equity Curve Chart
        const equityCtx = document.getElementById('equityChart').getContext('2d');
        const equityData = {json.dumps([p['portfolio_value'] for p in data['equity_curve']])};
        const labels = {json.dumps([p['timestamp'][:10] for p in data['equity_curve']])};
        
        new Chart(equityCtx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: 'Portfolio Value ($)',
                    data: equityData,
                    borderColor: '#4fc3f7',
                    backgroundColor: 'rgba(79, 195, 247, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#e0e6ed' }}
                    }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: '#1e3a5f' }},
                        ticks: {{ color: '#90a4ae' }}
                    }},
                    x: {{
                        grid: {{ color: '#1e3a5f' }},
                        ticks: {{ 
                            color: '#90a4ae',
                            maxTicksLimit: 10
                        }}
                    }}
                }}
            }}
        }});
        
        // Trade Distribution Chart
        const tradeCtx = document.getElementById('tradeChart').getContext('2d');
        const winningTrades = {data['summary']['winning_trades']};
        const losingTrades = {data['summary']['losing_trades']};
        
        new Chart(tradeCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Winning Trades', 'Losing Trades'],
                datasets: [{{
                    data: [winningTrades, losingTrades],
                    backgroundColor: ['#4caf50', '#f44336'],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{ color: '#e0e6ed' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
        
        return html
    
    def _generate_trades_rows(self, trades: List[Dict]) -> str:
        """Generate HTML table rows for trades"""
        rows = []
        for trade in trades:
            pnl_class = 'positive' if trade['pnl'] > 0 else 'negative'
            rows.append(f"""
                <tr>
                    <td>{trade['id']}</td>
                    <td>{trade['timestamp'][:16]}</td>
                    <td>{trade['signal_type']}</td>
                    <td>{trade['action']}</td>
                    <td>{trade['entry_price']:.4f}</td>
                    <td>{trade['exit_price']:.4f if trade['exit_price'] else '-'}</td>
                    <td>{trade['confidence']:.0f}%</td>
                    <td class="{pnl_class}">${trade['pnl']:.2f}</td>
                    <td class="{pnl_class}">{trade['pnl_percent']:.2f}%</td>
                    <td>{trade['exit_reason'] or '-'}</td>
                </tr>
            """)
        return ''.join(rows)
    
    def _generate_signal_type_cards(self, trades: List[Dict]) -> str:
        """Generate signal type performance cards"""
        # Group trades by signal type
        by_type = {}
        for trade in trades:
            st = trade['signal_type']
            if st not in by_type:
                by_type[st] = {'trades': [], 'pnl': 0}
            by_type[st]['trades'].append(trade)
            by_type[st]['pnl'] += trade['pnl']
        
        cards = []
        for st, data in sorted(by_type.items(), key=lambda x: abs(x[1]['pnl']), reverse=True)[:6]:
            trades_list = data['trades']
            wins = sum(1 for t in trades_list if t['pnl'] > 0)
            win_rate = wins / len(trades_list) if trades_list else 0
            avg_pnl = data['pnl'] / len(trades_list) if trades_list else 0
            
            cards.append(f"""
                <div class="signal-type-card">
                    <h4>{st}</h4>
                    <div class="stats">
                        <span>Trades: {len(trades_list)}</span>
                        <span>Win Rate: {win_rate:.1%}</span>
                    </div>
                    <div class="stats" style="margin-top: 8px;">
                        <span>Total P&L: ${data['pnl']:.2f}</span>
                        <span>Avg: ${avg_pnl:.2f}</span>
                    </div>
                </div>
            """)
        
        return ''.join(cards) if cards else '<p style="color: #90a4ae;">No signal data available</p>'
    
    def save_html_report(
        self,
        result: Any,
        strategy_name: str = "PriceOnlyStrategy",
        filename: Optional[str] = None
    ) -> str:
        """Save HTML report to file"""
        html = self.generate_html_report(result, strategy_name)
        
        if filename is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_report_{timestamp}.html"
        
        import os
        os.makedirs(self.output_dir, exist_ok=True)
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"HTML report saved to {filepath}")
        return filepath
    
    def generate_equity_curve_chart(
        self,
        equity_curve: List[Dict],
        filename: str = "equity_curve.png"
    ) -> str:
        """
        Generate equity curve chart image
        
        Note: Requires matplotlib. Returns path to saved image.
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from matplotlib.dates import DateFormatter
            
            timestamps = [datetime.fromisoformat(p['timestamp']) for p in equity_curve]
            values = [p['portfolio_value'] for p in equity_curve]
            
            plt.figure(figsize=(12, 6))
            plt.plot(timestamps, values, linewidth=2, color='#4fc3f7')
            plt.fill_between(timestamps, values, alpha=0.3, color='#4fc3f7')
            
            plt.title('Portfolio Equity Curve', fontsize=14, fontweight='bold')
            plt.xlabel('Date')
            plt.ylabel('Portfolio Value ($)')
            plt.grid(True, alpha=0.3)
            
            plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(timestamps)//10)))
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            
            import os
            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close()
            
            logger.info(f"Equity curve chart saved to {filepath}")
            return filepath
            
        except ImportError:
            logger.warning("matplotlib not installed. Cannot generate chart image.")
            return ""
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            return ""
