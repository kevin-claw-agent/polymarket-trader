"""
Backtest Reporter Module
Generates detailed reports from backtest results
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BacktestReporter:
    """Generates detailed backtest reports"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.output_dir = self.config.get('output_dir', 'backtest_results')
    
    def generate_report(
        self,
        result: Any,
        strategy_name: str = "PriceOnlyStrategy",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive backtest report
        
        Returns:
            Dictionary with report data
        """
        report = {
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'strategy': strategy_name,
                'version': '1.0.0'
            },
            'summary': result.to_dict()['summary'],
            'performance_analysis': self._analyze_performance(result),
            'trade_analysis': self._analyze_trades(result),
            'risk_analysis': self._analyze_risk(result),
            'signal_analysis': self._analyze_signals(result),
            'recommendations': self._generate_recommendations(result)
        }
        
        if metadata:
            report['metadata'].update(metadata)
        
        return report
    
    def _analyze_performance(self, result: Any) -> Dict[str, Any]:
        """Analyze performance metrics"""
        equity_curve = result.equity_curve
        
        if not equity_curve:
            return {'error': 'No equity curve data'}
        
        # Calculate monthly returns (if we have enough data)
        monthly_returns = self._calculate_monthly_returns(equity_curve)
        
        # Best and worst trades
        trades_by_pnl = sorted(result.trades, key=lambda t: t.pnl, reverse=True)
        best_trade = trades_by_pnl[0] if trades_by_pnl else None
        worst_trade = trades_by_pnl[-1] if trades_by_pnl else None
        
        # Consecutive wins/losses
        consecutive_stats = self._calculate_consecutive_stats(result.trades)
        
        return {
            'total_return_usd': round(result.total_return, 2),
            'total_return_percent': round(result.total_return_percent, 2),
            'cagr_percent': self._calculate_cagr(equity_curve),
            'monthly_returns': monthly_returns,
            'best_trade': {
                'pnl': round(best_trade.pnl, 2) if best_trade else 0,
                'pnl_percent': round(best_trade.pnl_percent, 2) if best_trade else 0,
                'signal_type': best_trade.signal_type if best_trade else None
            },
            'worst_trade': {
                'pnl': round(worst_trade.pnl, 2) if worst_trade else 0,
                'pnl_percent': round(worst_trade.pnl_percent, 2) if worst_trade else 0,
                'signal_type': worst_trade.signal_type if worst_trade else None
            },
            'consecutive_stats': consecutive_stats,
            'avg_trades_per_day': round(result.total_trades / max(len(equity_curve) / 24, 1), 2)
        }
    
    def _analyze_trades(self, result: Any) -> Dict[str, Any]:
        """Analyze trade statistics"""
        if not result.trades:
            return {'error': 'No trades to analyze'}
        
        # Group by signal type
        by_signal_type = {}
        for trade in result.trades:
            st = trade.signal_type
            if st not in by_signal_type:
                by_signal_type[st] = []
            by_signal_type[st].append(trade)
        
        signal_type_stats = {}
        for st, trades in by_signal_type.items():
            winning = [t for t in trades if t.pnl > 0]
            total_pnl = sum(t.pnl for t in trades)
            
            signal_type_stats[st] = {
                'count': len(trades),
                'win_count': len(winning),
                'win_rate': round(len(winning) / len(trades), 2) if trades else 0,
                'total_pnl': round(total_pnl, 2),
                'avg_pnl': round(total_pnl / len(trades), 2) if trades else 0,
                'avg_confidence': round(sum(t.confidence for t in trades) / len(trades), 1) if trades else 0
            }
        
        # Exit reasons
        exit_reasons = {}
        for trade in result.trades:
            reason = trade.exit_reason or 'unknown'
            if reason not in exit_reasons:
                exit_reasons[reason] = {'count': 0, 'win_count': 0, 'total_pnl': 0}
            exit_reasons[reason]['count'] += 1
            if trade.pnl > 0:
                exit_reasons[reason]['win_count'] += 1
            exit_reasons[reason]['total_pnl'] += trade.pnl
        
        # Calculate win rates by exit reason
        for reason in exit_reasons:
            stats = exit_reasons[reason]
            stats['win_rate'] = round(stats['win_count'] / stats['count'], 2) if stats['count'] > 0 else 0
            stats['total_pnl'] = round(stats['total_pnl'], 2)
        
        return {
            'by_signal_type': signal_type_stats,
            'by_exit_reason': exit_reasons,
            'long_trades': self._analyze_direction(result.trades, 'BUY'),
            'short_trades': self._analyze_direction(result.trades, 'SELL')
        }
    
    def _analyze_direction(self, trades: List, direction: str) -> Dict[str, Any]:
        """Analyze trades by direction (long/short)"""
        direction_trades = [t for t in trades if t.action == direction]
        
        if not direction_trades:
            return {'count': 0}
        
        winning = [t for t in direction_trades if t.pnl > 0]
        total_pnl = sum(t.pnl for t in direction_trades)
        
        return {
            'count': len(direction_trades),
            'win_count': len(winning),
            'win_rate': round(len(winning) / len(direction_trades), 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(total_pnl / len(direction_trades), 2)
        }
    
    def _analyze_risk(self, result: Any) -> Dict[str, Any]:
        """Analyze risk metrics"""
        return {
            'max_drawdown_usd': round(result.max_drawdown, 2),
            'max_drawdown_percent': round(result.max_drawdown_percent, 2),
            'sharpe_ratio': round(result.sharpe_ratio, 2),
            'volatility_annualized': round(result.volatility, 2),
            'calmar_ratio': self._calculate_calmar_ratio(result),
            'sortino_ratio': self._calculate_sortino_ratio(result),
            'var_95': self._calculate_var(result, 0.95),
            'expected_shortfall': self._calculate_expected_shortfall(result, 0.95)
        }
    
    def _analyze_signals(self, result: Any) -> Dict[str, Any]:
        """Analyze signal performance"""
        if not result.trades:
            return {'error': 'No signals to analyze'}
        
        # Confidence vs performance
        confidence_buckets = {
            '60-70': {'trades': [], 'pnl': 0},
            '70-80': {'trades': [], 'pnl': 0},
            '80-90': {'trades': [], 'pnl': 0},
            '90-100': {'trades': [], 'pnl': 0}
        }
        
        for trade in result.trades:
            conf = trade.confidence
            if 60 <= conf < 70:
                bucket = '60-70'
            elif 70 <= conf < 80:
                bucket = '70-80'
            elif 80 <= conf < 90:
                bucket = '80-90'
            else:
                bucket = '90-100'
            
            confidence_buckets[bucket]['trades'].append(trade)
            confidence_buckets[bucket]['pnl'] += trade.pnl
        
        confidence_analysis = {}
        for bucket, data in confidence_buckets.items():
            trades = data['trades']
            winning = [t for t in trades if t.pnl > 0]
            confidence_analysis[bucket] = {
                'count': len(trades),
                'win_rate': round(len(winning) / len(trades), 2) if trades else 0,
                'total_pnl': round(data['pnl'], 2),
                'avg_pnl': round(data['pnl'] / len(trades), 2) if trades else 0
            }
        
        return {
            'by_confidence': confidence_analysis,
            'total_signals': result.total_trades,
            'high_confidence_signals': sum(1 for t in result.trades if t.confidence >= 80)
        }
    
    def _generate_recommendations(self, result: Any) -> List[Dict[str, str]]:
        """Generate trading recommendations based on backtest"""
        recommendations = []
        
        # Win rate recommendations
        if result.win_rate < 0.4:
            recommendations.append({
                'type': 'warning',
                'message': 'Win rate below 40%. Consider tightening entry criteria or reducing position sizes.'
            })
        elif result.win_rate > 0.6:
            recommendations.append({
                'type': 'success',
                'message': f'Good win rate ({result.win_rate:.1%}). Strategy shows promise.'
            })
        
        # Drawdown recommendations
        if result.max_drawdown_percent > 20:
            recommendations.append({
                'type': 'warning',
                'message': f'High max drawdown ({result.max_drawdown_percent:.1f}%). Consider adding stop losses or position limits.'
            })
        
        # Sharpe ratio
        if result.sharpe_ratio < 1:
            recommendations.append({
                'type': 'info',
                'message': f'Low Sharpe ratio ({result.sharpe_ratio:.2f}). Risk-adjusted returns could be improved.'
            })
        elif result.sharpe_ratio > 2:
            recommendations.append({
                'type': 'success',
                'message': f'Excellent Sharpe ratio ({result.sharpe_ratio:.2f}). Good risk-adjusted returns.'
            })
        
        # Profit factor
        if result.profit_factor < 1.5:
            recommendations.append({
                'type': 'info',
                'message': f'Low profit factor ({result.profit_factor:.2f}). Winners should be larger relative to losers.'
            })
        
        # Hold time
        if result.avg_hold_time_hours > 48:
            recommendations.append({
                'type': 'info',
                'message': f'Long average hold time ({result.avg_hold_time_hours:.1f}h). Consider shorter targets for capital efficiency.'
            })
        
        if not recommendations:
            recommendations.append({
                'type': 'info',
                'message': 'Strategy shows balanced performance. Continue monitoring and consider forward testing.'
            })
        
        return recommendations
    
    def _calculate_monthly_returns(self, equity_curve: List[Dict]) -> List[Dict]:
        """Calculate monthly returns from equity curve"""
        if len(equity_curve) < 24:
            return []
        
        monthly = []
        current_month = None
        month_start_value = None
        
        for point in equity_curve:
            timestamp = datetime.fromisoformat(point['timestamp'])
            month_key = (timestamp.year, timestamp.month)
            
            if month_key != current_month:
                if current_month and month_start_value:
                    month_end_value = equity_curve[equity_curve.index(point) - 1]['portfolio_value']
                    monthly_return = (month_end_value - month_start_value) / month_start_value * 100
                    monthly.append({
                        'year': current_month[0],
                        'month': current_month[1],
                        'return_percent': round(monthly_return, 2)
                    })
                
                current_month = month_key
                month_start_value = point['portfolio_value']
        
        return monthly
    
    def _calculate_cagr(self, equity_curve: List[Dict]) -> float:
        """Calculate Compound Annual Growth Rate"""
        if len(equity_curve) < 2:
            return 0
        
        start_value = equity_curve[0]['portfolio_value']
        end_value = equity_curve[-1]['portfolio_value']
        
        start_time = datetime.fromisoformat(equity_curve[0]['timestamp'])
        end_time = datetime.fromisoformat(equity_curve[-1]['timestamp'])
        
        years = (end_time - start_time).days / 365.25
        
        if years < 0.01 or start_value <= 0:
            return 0
        
        cagr = ((end_value / start_value) ** (1 / years)) - 1
        return round(cagr * 100, 2)
    
    def _calculate_consecutive_stats(self, trades: List) -> Dict[str, Any]:
        """Calculate consecutive win/loss statistics"""
        if not trades:
            return {}
        
        # Sort by exit time
        sorted_trades = sorted(trades, key=lambda t: t.exit_time or datetime.min)
        
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in sorted_trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        return {
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses
        }
    
    def _calculate_calmar_ratio(self, result: Any) -> float:
        """Calculate Calmar ratio (CAGR / Max Drawdown)"""
        if result.max_drawdown_percent <= 0:
            return 0
        
        cagr = result.total_return_percent  # Simplified
        return round(cagr / result.max_drawdown_percent, 2)
    
    def _calculate_sortino_ratio(self, result: Any) -> float:
        """Calculate Sortino ratio (focus on downside risk)"""
        returns = []
        for trade in result.trades:
            if trade.position_size > 0:
                r = trade.pnl / trade.position_size
                returns.append(r)
        
        if not returns:
            return 0
        
        avg_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < 0]
        
        if not downside_returns:
            return float('inf')
        
        downside_std = (sum(r ** 2 for r in downside_returns) / len(downside_returns)) ** 0.5
        
        if downside_std == 0:
            return 0
        
        return round(avg_return / downside_std, 2)
    
    def _calculate_var(self, result: Any, confidence: float = 0.95) -> float:
        """Calculate Value at Risk"""
        returns = sorted([t.pnl for t in result.trades])
        if not returns:
            return 0
        
        index = int(len(returns) * (1 - confidence))
        return round(returns[max(0, index)], 2)
    
    def _calculate_expected_shortfall(self, result: Any, confidence: float = 0.95) -> float:
        """Calculate Expected Shortfall (CVaR)"""
        returns = sorted([t.pnl for t in result.trades])
        if not returns:
            return 0
        
        index = int(len(returns) * (1 - confidence))
        tail_returns = returns[:max(1, index)]
        
        if not tail_returns:
            return 0
        
        return round(sum(tail_returns) / len(tail_returns), 2)
    
    def save_report(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """Save report to file"""
        if filename is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_report_{timestamp}.json"
        
        import os
        os.makedirs(self.output_dir, exist_ok=True)
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to {filepath}")
        return filepath
    
    def print_summary(self, result: Any):
        """Print a text summary to console"""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"\nTotal Trades:        {result.total_trades}")
        print(f"Winning Trades:      {result.winning_trades} ({result.win_rate:.1%})")
        print(f"Losing Trades:       {result.losing_trades}")
        print(f"\nTotal Return:        ${result.total_return:.2f} ({result.total_return_percent:.2f}%)")
        print(f"Max Drawdown:        ${result.max_drawdown:.2f} ({result.max_drawdown_percent:.2f}%)")
        print(f"Sharpe Ratio:        {result.sharpe_ratio:.2f}")
        print(f"Profit Factor:       {result.profit_factor:.2f}")
        print(f"Avg Hold Time:       {result.avg_hold_time_hours:.1f} hours")
        print("=" * 60 + "\n")
