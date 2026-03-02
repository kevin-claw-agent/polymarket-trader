"""
Backtest Engine Module
Main backtesting engine for simulating trades
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    STOPPED = "stopped"
    TAKE_PROFIT = "take_profit"
    EXPIRED = "expired"


@dataclass
class Trade:
    """Represents a single trade"""
    id: str
    market_id: str
    timestamp: datetime
    signal_type: str
    action: str  # BUY or SELL
    entry_price: float
    position_size: float
    confidence: float
    stop_loss: float
    take_profit: float
    max_hold_periods: int
    
    # Execution tracking
    status: TradeStatus = TradeStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Runtime tracking
    max_price: float = field(default=0.0)
    min_price: float = field(default=0.0)
    hold_periods: int = 0


@dataclass
class BacktestResult:
    """Results from a backtest run"""
    # Overall stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Returns
    total_return: float = 0.0
    total_return_percent: float = 0.0
    avg_return_per_trade: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    volatility: float = 0.0
    
    # Trade metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_hold_time_hours: float = 0.0
    
    # Signal metrics
    total_signals: int = 0
    signals_executed: int = 0
    signals_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Equity curve
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    
    # Trades
    trades: List[Trade] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'summary': {
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': round(self.win_rate, 2),
                'total_return': round(self.total_return, 2),
                'total_return_percent': round(self.total_return_percent, 2),
                'avg_return_per_trade': round(self.avg_return_per_trade, 2),
                'max_drawdown': round(self.max_drawdown, 2),
                'max_drawdown_percent': round(self.max_drawdown_percent, 2),
                'sharpe_ratio': round(self.sharpe_ratio, 2),
                'volatility': round(self.volatility, 2),
                'profit_factor': round(self.profit_factor, 2),
                'avg_win': round(self.avg_win, 2),
                'avg_loss': round(self.avg_loss, 2),
                'avg_hold_time_hours': round(self.avg_hold_time_hours, 1),
                'total_signals': self.total_signals,
                'signals_executed': self.signals_executed
            },
            'signals_by_type': self.signals_by_type,
            'equity_curve': self.equity_curve,
            'trades': [
                {
                    'id': t.id,
                    'market_id': t.market_id,
                    'timestamp': t.timestamp.isoformat(),
                    'signal_type': t.signal_type,
                    'action': t.action,
                    'entry_price': t.entry_price,
                    'position_size': t.position_size,
                    'confidence': t.confidence,
                    'stop_loss': t.stop_loss,
                    'take_profit': t.take_profit,
                    'status': t.status.value,
                    'exit_price': t.exit_price,
                    'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                    'exit_reason': t.exit_reason,
                    'pnl': round(t.pnl, 4),
                    'pnl_percent': round(t.pnl_percent, 4),
                    'hold_periods': t.hold_periods
                }
                for t in self.trades
            ]
        }


class BacktestEngine:
    """
    Main backtesting engine
    Simulates trading execution and calculates performance metrics
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('backtest', {})
        
        # Portfolio settings
        self.initial_capital = self.config.get('initial_capital', 10000)
        self.position_size = self.config.get('position_size', 0.02)
        self.max_positions = self.config.get('max_positions', 10)
        self.fee_rate = self.config.get('fee_rate', 0.002)
        
        # Risk settings
        self.stop_loss_enabled = self.config.get('stop_loss_enabled', True)
        self.take_profit_enabled = self.config.get('take_profit_enabled', True)
        self.max_hold_hours = self.config.get('max_hold_hours', 48)
        
        # Tracking
        self.portfolio_value: float = self.initial_capital
        self.cash: float = self.initial_capital
        self.positions: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        self.trade_counter: int = 0
        
    def run_backtest(
        self,
        signals: List[Dict[str, Any]],
        price_data: Dict[str, List[Dict[str, Any]]]
    ) -> BacktestResult:
        """
        Run backtest with given signals and price data
        
        Args:
            signals: List of signals from strategy
            price_data: Dict mapping market_id to price history
        
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(f"Starting backtest with {len(signals)} signals")
        
        # Sort signals by timestamp
        sorted_signals = sorted(signals, key=lambda x: x['timestamp'])
        
        # Build timeline of all price updates
        timeline = self._build_timeline(price_data)
        
        # Process each time step
        for timestamp, updates in timeline:
            # Update portfolio value
            self._update_portfolio(timestamp, updates)
            
            # Check for signals at this timestamp
            signals_at_time = [
                s for s in sorted_signals
                if s['timestamp'] == timestamp.isoformat()
            ]
            
            for signal in signals_at_time:
                self._execute_signal(signal, timestamp, updates)
            
            # Check stop losses and take profits
            self._check_exits(timestamp, updates)
            
            # Record equity
            self._record_equity(timestamp)
        
        # Close any remaining positions at final price
        self._close_all_positions(timeline[-1][0] if timeline else datetime.utcnow())
        
        # Calculate results
        result = self._calculate_results()
        
        logger.info(f"Backtest complete: {result.total_trades} trades, "
                   f"{result.win_rate:.1%} win rate, "
                   f"{result.total_return_percent:.2f}% return")
        
        return result
    
    def _build_timeline(
        self,
        price_data: Dict[str, List[Dict]]
    ) -> List[tuple]:
        """Build chronological timeline of price updates"""
        events = []
        
        for market_id, data in price_data.items():
            for point in data:
                timestamp = datetime.fromisoformat(point['timestamp'])
                events.append((timestamp, market_id, point))
        
        # Sort by timestamp
        events.sort(key=lambda x: x[0])
        
        # Group by timestamp
        timeline = []
        current_time = None
        current_updates = {}
        
        for timestamp, market_id, point in events:
            if timestamp != current_time:
                if current_time:
                    timeline.append((current_time, current_updates))
                current_time = timestamp
                current_updates = {}
            current_updates[market_id] = point
        
        if current_time:
            timeline.append((current_time, current_updates))
        
        return timeline
    
    def _execute_signal(
        self,
        signal: Dict,
        timestamp: datetime,
        price_updates: Dict[str, Dict]
    ):
        """Execute a trading signal"""
        market_id = signal['market_id']
        
        # Check if already in position
        if market_id in self.positions:
            return
        
        # Check max positions
        if len(self.positions) >= self.max_positions:
            return
        
        # Get current price
        if market_id not in price_updates:
            return
        
        current_price = price_updates[market_id]['price']
        
        # Calculate position size
        position_value = self.portfolio_value * self.position_size
        
        # Check if enough cash
        if position_value > self.cash:
            position_value = self.cash * 0.95
        
        # Create trade
        self.trade_counter += 1
        trade = Trade(
            id=f"trade_{self.trade_counter:04d}",
            market_id=market_id,
            timestamp=timestamp,
            signal_type=signal['signal_type'],
            action=signal['action'],
            entry_price=current_price,
            position_size=position_value,
            confidence=signal['confidence'],
            stop_loss=signal.get('stop_loss', current_price * 0.97),
            take_profit=signal.get('take_profit', current_price * 1.05),
            max_hold_periods=signal.get('hold_periods', 24),
            max_price=current_price,
            min_price=current_price
        )
        
        # Deduct cash (including fees)
        fee = position_value * self.fee_rate
        self.cash -= position_value + fee
        
        # Add to positions
        self.positions[market_id] = trade
        
        logger.debug(f"Opened {trade.action} position in {market_id} at {current_price}")
    
    def _check_exits(
        self,
        timestamp: datetime,
        price_updates: Dict[str, Dict]
    ):
        """Check for stop loss and take profit triggers"""
        for market_id, trade in list(self.positions.items()):
            if market_id not in price_updates:
                continue
            
            current_price = price_updates[market_id]['price']
            
            # Update tracking
            trade.max_price = max(trade.max_price, current_price)
            trade.min_price = min(trade.min_price, current_price)
            trade.hold_periods += 1
            
            # Check stop loss
            if self.stop_loss_enabled:
                if trade.action == 'BUY' and current_price <= trade.stop_loss:
                    self._close_trade(trade, timestamp, current_price, 'stop_loss')
                    continue
                elif trade.action == 'SELL' and current_price >= trade.stop_loss:
                    self._close_trade(trade, timestamp, current_price, 'stop_loss')
                    continue
            
            # Check take profit
            if self.take_profit_enabled:
                if trade.action == 'BUY' and current_price >= trade.take_profit:
                    self._close_trade(trade, timestamp, current_price, 'take_profit')
                    continue
                elif trade.action == 'SELL' and current_price <= trade.take_profit:
                    self._close_trade(trade, timestamp, current_price, 'take_profit')
                    continue
            
            # Check max hold time
            if trade.hold_periods >= trade.max_hold_periods:
                self._close_trade(trade, timestamp, current_price, 'max_hold_time')
                continue
    
    def _close_trade(
        self,
        trade: Trade,
        timestamp: datetime,
        exit_price: float,
        reason: str
    ):
        """Close a trade and calculate P&L"""
        trade.exit_price = exit_price
        trade.exit_time = timestamp
        trade.exit_reason = reason
        
        # Calculate P&L
        if trade.action == 'BUY':
            price_return = (exit_price - trade.entry_price) / trade.entry_price
        else:  # SELL
            price_return = (trade.entry_price - exit_price) / trade.entry_price
        
        # Apply fees (entry and exit)
        total_fees = trade.position_size * self.fee_rate * 2
        
        trade.pnl = trade.position_size * price_return - total_fees
        trade.pnl_percent = price_return * 100
        
        # Update status
        if reason == 'stop_loss':
            trade.status = TradeStatus.STOPPED
        elif reason == 'take_profit':
            trade.status = TradeStatus.TAKE_PROFIT
        else:
            trade.status = TradeStatus.CLOSED
        
        # Return cash to portfolio
        self.cash += trade.position_size + trade.pnl
        
        # Move to closed trades
        del self.positions[trade.market_id]
        self.closed_trades.append(trade)
        
        logger.debug(f"Closed {trade.action} position in {trade.market_id}: "
                    f"{trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
    
    def _update_portfolio(
        self,
        timestamp: datetime,
        price_updates: Dict[str, Dict]
    ):
        """Update portfolio value based on current prices"""
        position_value = 0
        
        for market_id, trade in self.positions.items():
            if market_id in price_updates:
                current_price = price_updates[market_id]['price']
                
                if trade.action == 'BUY':
                    value = trade.position_size * (current_price / trade.entry_price)
                else:
                    value = trade.position_size * (2 - current_price / trade.entry_price)
                
                position_value += value
        
        self.portfolio_value = self.cash + position_value
    
    def _record_equity(self, timestamp: datetime):
        """Record equity curve point"""
        self.equity_curve.append({
            'timestamp': timestamp.isoformat(),
            'portfolio_value': round(self.portfolio_value, 2),
            'cash': round(self.cash, 2),
            'position_value': round(self.portfolio_value - self.cash, 2),
            'open_positions': len(self.positions)
        })
    
    def _close_all_positions(self, final_timestamp: datetime):
        """Close all open positions at final timestamp"""
        for market_id, trade in list(self.positions.items()):
            # Use last known price or entry price
            exit_price = trade.entry_price
            self._close_trade(trade, final_timestamp, exit_price, 'backtest_end')
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate final backtest results"""
        result = BacktestResult()
        
        # Basic counts
        result.total_trades = len(self.closed_trades)
        result.trades = self.closed_trades
        
        if result.total_trades == 0:
            return result
        
        # Winning/losing trades
        winning_trades = [t for t in self.closed_trades if t.pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl <= 0]
        
        result.winning_trades = len(winning_trades)
        result.losing_trades = len(losing_trades)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
        
        # Returns
        result.total_return = sum(t.pnl for t in self.closed_trades)
        result.total_return_percent = (result.total_return / self.initial_capital) * 100
        result.avg_return_per_trade = result.total_return / result.total_trades
        
        # Win/loss statistics
        if winning_trades:
            result.avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades)
        
        if losing_trades:
            result.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades)
        
        # Profit factor
        total_wins = sum(t.pnl for t in winning_trades) if winning_trades else 0
        total_losses = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 1
        result.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Hold time
        hold_times = []
        for trade in self.closed_trades:
            if trade.exit_time and trade.timestamp:
                hold_time = (trade.exit_time - trade.timestamp).total_seconds() / 3600
                hold_times.append(hold_time)
        
        if hold_times:
            result.avg_hold_time_hours = np.mean(hold_times)
        
        # Max drawdown
        result.max_drawdown, result.max_drawdown_percent = self._calculate_max_drawdown()
        
        # Sharpe ratio
        result.sharpe_ratio = self._calculate_sharpe_ratio()
        result.volatility = self._calculate_volatility()
        
        # Equity curve
        result.equity_curve = self.equity_curve
        
        # Signal type breakdown
        signal_types = {}
        for trade in self.closed_trades:
            st = trade.signal_type
            signal_types[st] = signal_types.get(st, 0) + 1
        result.signals_by_type = signal_types
        
        return result
    
    def _calculate_max_drawdown(self) -> tuple:
        """Calculate maximum drawdown"""
        if not self.equity_curve:
            return 0, 0
        
        peak = self.initial_capital
        max_dd = 0
        max_dd_pct = 0
        
        for point in self.equity_curve:
            value = point['portfolio_value']
            if value > peak:
                peak = value
            
            dd = peak - value
            dd_pct = (dd / peak) * 100 if peak > 0 else 0
            
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        
        return max_dd, max_dd_pct
    
    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio"""
        if not self.equity_curve or len(self.equity_curve) < 2:
            return 0
        
        # Calculate returns
        values = [p['portfolio_value'] for p in self.equity_curve]
        returns = []
        for i in range(1, len(values)):
            r = (values[i] - values[i-1]) / values[i-1] if values[i-1] > 0 else 0
            returns.append(r)
        
        if not returns:
            return 0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Annualize (assuming hourly data)
        periods_per_year = 365 * 24
        sharpe = 0
        if std_return > 0:
            sharpe = (avg_return * periods_per_year - risk_free_rate) / (std_return * np.sqrt(periods_per_year))
        
        return sharpe
    
    def _calculate_volatility(self) -> float:
        """Calculate annualized volatility"""
        if not self.equity_curve or len(self.equity_curve) < 2:
            return 0
        
        values = [p['portfolio_value'] for p in self.equity_curve]
        returns = []
        for i in range(1, len(values)):
            r = (values[i] - values[i-1]) / values[i-1] if values[i-1] > 0 else 0
            returns.append(r)
        
        if not returns:
            return 0
        
        # Annualize
        periods_per_year = 365 * 24
        return np.std(returns) * np.sqrt(periods_per_year) * 100
