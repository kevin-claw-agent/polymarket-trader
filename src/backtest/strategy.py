"""
Backtest Strategy Module
Simplified strategy using only price signals (no news sentiment)
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class PriceOnlyStrategy:
    """
    Simplified strategy that uses only price data
    Detects overreactions based on:
    - Price volatility
    - Volume surges
    - Mean reversion patterns
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('strategy', {})
        
        # Detection parameters
        self.price_spike_threshold = self.config.get('price_spike_threshold', 0.05)
        self.volume_surge_threshold = self.config.get('volume_surge_threshold', 3.0)
        self.lookback_periods = self.config.get('lookback_periods', 20)
        
        # Mean reversion parameters
        self.mean_reversion_threshold = self.config.get('mean_reversion_threshold', 0.02)
        self.min_zscore = self.config.get('min_zscore', 2.0)
        
        # Signal parameters
        self.min_confidence = self.config.get('min_confidence', 60)
        self.cooldown_bars = self.config.get('cooldown_bars', 6)
        
        # Track cooldowns
        self.last_signal_time: Dict[str, datetime] = {}
        
    def detect_signals(
        self,
        market_id: str,
        price_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect trading signals from price data only
        
        Returns:
            List of signal dictionaries
        """
        if len(price_data) < self.lookback_periods + 5:
            return []
        
        signals = []
        
        for i in range(self.lookback_periods, len(price_data) - 1):
            window_data = price_data[i - self.lookback_periods:i]
            current_data = price_data[i]
            
            signal = self._check_for_signal(
                market_id,
                window_data,
                current_data,
                price_data[i + 1:]  # Future data for outcome
            )
            
            if signal:
                # Check cooldown
                signal_time = datetime.fromisoformat(current_data['timestamp'])
                if market_id in self.last_signal_time:
                    time_since_last = signal_time - self.last_signal_time[market_id]
                    if time_since_last < timedelta(hours=self.cooldown_bars):
                        continue
                
                self.last_signal_time[market_id] = signal_time
                signals.append(signal)
        
        return signals
    
    def _check_for_signal(
        self,
        market_id: str,
        window_data: List[Dict],
        current_data: Dict,
        future_data: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Check if current conditions generate a signal"""
        
        prices = [d['price'] for d in window_data]
        volumes = [d.get('volume', 0) for d in window_data]
        
        current_price = current_data['price']
        current_volume = current_data.get('volume', 0)
        current_time = datetime.fromisoformat(current_data['timestamp'])
        
        # Calculate metrics
        price_ma = np.mean(prices)
        price_std = np.std(prices)
        volume_ma = np.mean(volumes)
        
        # Z-score (how many std devs from mean)
        if price_std > 0:
            zscore = (current_price - price_ma) / price_std
        else:
            zscore = 0
        
        # Price change from MA
        price_change_from_ma = (current_price - price_ma) / price_ma if price_ma > 0 else 0
        
        # Volume ratio
        volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1.0
        
        # Detect overreaction signals
        signal_type = None
        confidence = 0
        
        # Signal 1: Mean reversion (extreme z-score + volume surge)
        if abs(zscore) >= self.min_zscore and volume_ratio >= self.volume_surge_threshold:
            if zscore > 0:
                signal_type = 'MEAN_REVERSION_SHORT'
                confidence = min(100, 60 + abs(zscore) * 10 + (volume_ratio - 1) * 5)
            else:
                signal_type = 'MEAN_REVERSION_LONG'
                confidence = min(100, 60 + abs(zscore) * 10 + (volume_ratio - 1) * 5)
        
        # Signal 2: Sharp price spike with volume
        elif abs(price_change_from_ma) >= self.price_spike_threshold and volume_ratio >= 2.0:
            if price_change_from_ma > 0:
                signal_type = 'SPIKE_SHORT'
                confidence = min(100, 55 + abs(price_change_from_ma) * 200 + (volume_ratio - 1) * 3)
            else:
                signal_type = 'SPIKE_LONG'
                confidence = min(100, 55 + abs(price_change_from_ma) * 200 + (volume_ratio - 1) * 3)
        
        # Signal 3: Extreme volatility
        elif abs(zscore) >= 3.0:
            if zscore > 0:
                signal_type = 'EXTREME_VOLATILITY_SHORT'
            else:
                signal_type = 'EXTREME_VOLATILITY_LONG'
            confidence = min(100, 50 + abs(zscore) * 10)
        
        if signal_type and confidence >= self.min_confidence:
            # Calculate expected outcome
            expected_return = self._calculate_expected_return(
                signal_type, current_price, prices, future_data
            )
            
            return {
                'market_id': market_id,
                'timestamp': current_data['timestamp'],
                'signal_type': signal_type,
                'action': 'SELL' if 'SHORT' in signal_type or current_price > 0.5 else 'BUY',
                'current_price': current_price,
                'confidence': confidence,
                'metrics': {
                    'zscore': round(zscore, 3),
                    'price_change_from_ma': round(price_change_from_ma, 4),
                    'volume_ratio': round(volume_ratio, 2),
                    'price_ma': round(price_ma, 4),
                    'price_std': round(price_std, 4)
                },
                'expected_return': expected_return,
                'stop_loss': self._calculate_stop_loss(signal_type, current_price),
                'take_profit': self._calculate_take_profit(signal_type, current_price),
                'hold_periods': self._estimate_hold_periods(signal_type)
            }
        
        return None
    
    def _calculate_expected_return(
        self,
        signal_type: str,
        entry_price: float,
        historical_prices: List[float],
        future_data: List[Dict]
    ) -> float:
        """Calculate expected return based on signal type and historical patterns"""
        
        # Simple mean reversion assumption
        price_ma = np.mean(historical_prices)
        
        if 'LONG' in signal_type:
            # Expect price to rise
            target = min(price_ma * 1.05, 0.95)
            return (target - entry_price) / entry_price if entry_price > 0 else 0
        else:
            # Expect price to fall
            target = max(price_ma * 0.95, 0.05)
            return (entry_price - target) / entry_price if entry_price > 0 else 0
    
    def _calculate_stop_loss(
        self,
        signal_type: str,
        entry_price: float
    ) -> float:
        """Calculate stop loss price"""
        stop_distance = 0.03  # 3% stop
        
        if 'LONG' in signal_type:
            return max(0.01, entry_price - stop_distance)
        else:
            return min(0.99, entry_price + stop_distance)
    
    def _calculate_take_profit(
        self,
        signal_type: str,
        entry_price: float
    ) -> float:
        """Calculate take profit price"""
        target_distance = 0.05  # 5% target
        
        if 'LONG' in signal_type:
            return min(0.99, entry_price + target_distance)
        else:
            return max(0.01, entry_price - target_distance)
    
    def _estimate_hold_periods(self, signal_type: str) -> int:
        """Estimate hold time in hours"""
        if 'MEAN_REVERSION' in signal_type:
            return 24  # 1 day
        elif 'SPIKE' in signal_type:
            return 12  # 12 hours
        else:
            return 48  # 2 days
    
    def calculate_position_size(
        self,
        confidence: float,
        portfolio_value: float
    ) -> float:
        """Calculate position size based on confidence"""
        base_size = 0.02  # 2% base
        max_size = 0.05   # 5% max
        
        # Scale by confidence
        confidence_factor = confidence / 100
        size = base_size * (1 + confidence_factor)
        
        return min(size, max_size) * portfolio_value


class SimpleMomentumStrategy:
    """
    Simple momentum-based strategy
    Buys on upward momentum, sells on downward momentum
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('strategy', {})
        self.lookback = self.config.get('momentum_lookback', 5)
        self.threshold = self.config.get('momentum_threshold', 0.02)
        self.min_confidence = self.config.get('min_confidence', 60)
    
    def detect_signals(
        self,
        market_id: str,
        price_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect momentum signals"""
        if len(price_data) < self.lookback + 5:
            return []
        
        signals = []
        
        for i in range(self.lookback, len(price_data) - 1):
            window = price_data[i - self.lookback:i]
            current = price_data[i]
            
            prices = [d['price'] for d in window]
            momentum = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
            
            current_price = current['price']
            
            if abs(momentum) >= self.threshold:
                if momentum > 0:
                    signal_type = 'MOMENTUM_LONG'
                    action = 'BUY'
                else:
                    signal_type = 'MOMENTUM_SHORT'
                    action = 'SELL'
                
                confidence = min(100, 50 + abs(momentum) * 500)
                
                if confidence >= self.min_confidence:
                    signals.append({
                        'market_id': market_id,
                        'timestamp': current['timestamp'],
                        'signal_type': signal_type,
                        'action': action,
                        'current_price': current_price,
                        'confidence': confidence,
                        'metrics': {
                            'momentum': round(momentum, 4),
                            'lookback': self.lookback
                        },
                        'expected_return': abs(momentum) * 1.5,
                        'stop_loss': current_price * 0.97 if action == 'BUY' else current_price * 1.03,
                        'take_profit': current_price * 1.05 if action == 'BUY' else current_price * 0.95,
                        'hold_periods': 12
                    })
        
        return signals
