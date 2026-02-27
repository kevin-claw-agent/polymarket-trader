"""
Risk Manager Module
Manages trading risk and exposure limits
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import logging
import asyncio

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk exposure and trading limits"""
    
    def __init__(self, config: Dict[str, Any], database):
        self.config = config
        self.db = database
        
        # Risk settings
        self.enabled = config.get('enabled', True)
        self.exposure = config.get('exposure', {})
        self.loss_limits = config.get('loss_limits', {})
        self.circuit_breakers = config.get('circuit_breakers', {})
        
        # Limits
        self.max_per_market = self.exposure.get('max_per_market', 0.05)
        self.max_total = self.exposure.get('max_total', 0.50)
        self.max_correlated = self.exposure.get('max_correlated', 0.15)
        
        self.max_daily_loss = self.loss_limits.get('max_daily_loss', 0.02)
        self.max_weekly_loss = self.loss_limits.get('max_weekly_loss', 0.05)
        self.emergency_stop = self.loss_limits.get('emergency_stop_loss', 0.10)
        
        # Circuit breaker state
        self.circuit_breaker_triggered = False
        self.circuit_breaker_until = None
        
        # Correlation groups
        self.correlation_groups = {
            'crypto': ['bitcoin', 'ethereum', 'crypto', 'blockchain', 'btc', 'eth'],
            'tech_stocks': ['apple', 'microsoft', 'google', 'amazon', 'tech'],
            'election': ['trump', 'biden', 'election', 'vote', 'president'],
            'sports_nfl': ['nfl', 'football', 'super bowl'],
            'sports_nba': ['nba', 'basketball']
        }
    
    async def approve_signal(self, signal: Dict[str, Any]) -> bool:
        """Check if signal passes all risk checks"""
        if not self.enabled:
            return True
        
        checks = [
            self._check_circuit_breaker(),
            self._check_exposure_limits(signal),
            self._check_daily_loss_limit(),
            self._check_correlation_limits(signal),
            self._check_signal_risk_reward(signal),
            self._check_trading_hours()
        ]
        
        passed = all(checks)
        
        if not passed:
            logger.warning(f"Signal {signal.get('id')} failed risk checks")
        
        return passed
    
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is active"""
        if not self.circuit_breakers.get('enabled', True):
            return True
        
        if self.circuit_breaker_triggered:
            if self.circuit_breaker_until and datetime.utcnow() > self.circuit_breaker_until:
                # Reset circuit breaker
                self.circuit_breaker_triggered = False
                self.circuit_breaker_until = None
                logger.info("Circuit breaker reset")
                return True
            return False
        
        return True
    
    async def _check_exposure_limits(self, signal: Dict[str, Any]) -> bool:
        """Check position size against exposure limits"""
        market_id = signal['market']['id']
        position_size = signal['signal']['position_size']
        
        # Get current exposure
        current_exposure = await self.db.get_market_exposure(market_id)
        total_exposure = await self.db.get_total_exposure()
        
        # Check per-market limit
        new_market_exposure = current_exposure + position_size
        if new_market_exposure > self.max_per_market:
            logger.warning(
                f"Per-market exposure limit exceeded: {new_market_exposure:.2%} > {self.max_per_market:.2%}"
            )
            return False
        
        # Check total exposure
        new_total_exposure = total_exposure + position_size
        if new_total_exposure > self.max_total:
            logger.warning(
                f"Total exposure limit exceeded: {new_total_exposure:.2%} > {self.max_total:.2%}"
            )
            return False
        
        return True
    
    async def _check_daily_loss_limit(self) -> bool:
        """Check daily loss limit"""
        daily_pnl = await self.db.get_daily_pnl()
        
        if daily_pnl <= -self.max_daily_loss:
            logger.warning(f"Daily loss limit reached: {daily_pnl:.2%}")
            return False
        
        return True
    
    async def _check_correlation_limits(self, signal: Dict[str, Any]) -> bool:
        """Check correlation group exposure"""
        market_question = signal['market']['question'].lower()
        category = signal['market'].get('category', 'general')
        position_size = signal['signal']['position_size']
        
        # Find which correlation groups this market belongs to
        matching_groups = []
        for group_name, keywords in self.correlation_groups.items():
            if any(kw in market_question for kw in keywords) or category in group_name:
                matching_groups.append(group_name)
        
        # Check exposure in each matching group
        for group in matching_groups:
            group_exposure = await self.db.get_correlated_exposure(group)
            new_exposure = group_exposure + position_size
            
            if new_exposure > self.max_correlated:
                logger.warning(
                    f"Correlation group '{group}' limit exceeded: {new_exposure:.2%}"
                )
                return False
        
        return True
    
    def _check_signal_risk_reward(self, signal: Dict[str, Any]) -> bool:
        """Check if signal meets minimum risk-reward ratio"""
        risk_reward = signal['signal'].get('risk_reward_ratio', 0)
        
        # Minimum 1.5:1 risk-reward
        if risk_reward < 1.5:
            logger.warning(f"Risk-reward ratio too low: {risk_reward:.2f}")
            return False
        
        return True
    
    def _check_trading_hours(self) -> bool:
        """Check if within allowed trading hours"""
        # For now, allow trading 24/7
        # Can be extended to restrict certain market types
        return True
    
    async def check_and_trigger_circuit_breaker(self, market_data: List[Dict]):
        """Check if circuit breaker should be triggered"""
        if not self.circuit_breakers.get('enabled', True):
            return
        
        if self.circuit_breaker_triggered:
            return
        
        threshold = self.circuit_breakers.get('volatility_threshold', 0.30)
        
        # Check for extreme volatility in any market
        for market in market_data:
            price_data = market.get('price_data', {})
            change_5m = price_data.get('change_5m', {}).get('percent', 0)
            change_1h = price_data.get('change_1h', {}).get('percent', 0)
            
            if abs(change_5m) >= threshold * 100 or abs(change_1h) >= threshold * 100:
                await self._trigger_circuit_breaker(market, max(abs(change_5m), abs(change_1h)))
                return
    
    async def _trigger_circuit_breaker(self, market: Dict, volatility: float):
        """Trigger circuit breaker"""
        cooldown_minutes = self.circuit_breakers.get('cooldown_minutes', 60)
        
        self.circuit_breaker_triggered = True
        self.circuit_breaker_until = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
        
        logger.critical(
            f"CIRCUIT BREAKER TRIGGERED: {market.get('market_question', 'Unknown')} "
            f"volatility {volatility:.1f}%"
        )
        
        # Log to database
        await self.db.log_circuit_breaker({
            'timestamp': datetime.utcnow().isoformat(),
            'market_id': market.get('market_id'),
            'volatility': volatility,
            'cooldown_until': self.circuit_breaker_until.isoformat()
        })
        
        # Send emergency alert
        # This would be implemented in the alert system
    
    async def update_position_risk(self, signal_id: str, current_price: float):
        """Update risk metrics for an open position"""
        try:
            signal = await self.db.get_signal(signal_id)
            if not signal or signal['status'] != 'active':
                return
            
            entry_price = signal['execution'].get('executed_price', signal['signal']['entry_price'])
            stop_loss = signal['signal']['stop_loss']
            action = signal['signal']['action']
            
            # Calculate current PnL
            if action == 'BUY':
                pnl = (current_price - entry_price) / entry_price
                # Check if stop loss hit
                if current_price <= stop_loss:
                    await self._close_position(signal_id, current_price, pnl, 'stop_loss')
                    return
            else:  # SELL
                pnl = (entry_price - current_price) / entry_price
                # Check if stop loss hit
                if current_price >= stop_loss:
                    await self._close_position(signal_id, current_price, pnl, 'stop_loss')
                    return
            
            # Check emergency stop
            if pnl <= -self.emergency_stop:
                logger.critical(f"Emergency stop triggered for {signal_id}: {pnl:.2%}")
                await self._close_position(signal_id, current_price, pnl, 'emergency_stop')
                return
            
            # Check take profit
            take_profit = signal['signal']['take_profit']
            if action == 'BUY' and current_price >= take_profit:
                await self._close_position(signal_id, current_price, pnl, 'take_profit')
                return
            elif action == 'SELL' and current_price <= take_profit:
                await self._close_position(signal_id, current_price, pnl, 'take_profit')
                return
            
            # Update running PnL
            await self.db.update_position_pnl(signal_id, pnl)
            
        except Exception as e:
            logger.error(f"Error updating position risk: {e}")
    
    async def _close_position(
        self,
        signal_id: str,
        exit_price: float,
        pnl: float,
        reason: str
    ):
        """Close a position"""
        from src.signals.generator import SignalGenerator
        
        generator = SignalGenerator(self.config, self.db)
        await generator.close_signal(signal_id, exit_price, pnl)
        
        logger.info(f"Position {signal_id} closed via {reason} at {pnl:.2%} PnL")
        
        # Log to database
        await self.db.log_trade_close({
            'signal_id': signal_id,
            'exit_price': exit_price,
            'pnl': pnl,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def get_risk_report(self) -> Dict[str, Any]:
        """Generate risk report"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'circuit_breaker': {
                'active': self.circuit_breaker_triggered,
                'until': self.circuit_breaker_until.isoformat() if self.circuit_breaker_until else None
            },
            'exposure': {
                'total': await self.db.get_total_exposure(),
                'max_total': self.max_total,
                'utilization': (await self.db.get_total_exposure()) / self.max_total
            },
            'daily_pnl': await self.db.get_daily_pnl(),
            'weekly_pnl': await self.db.get_weekly_pnl(),
            'open_positions': await self.db.get_open_positions_count(),
            'loss_limit_remaining': self.max_daily_loss - await self.db.get_daily_pnl()
        }
