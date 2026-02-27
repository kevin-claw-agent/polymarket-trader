"""
Market Monitor Module
Detects price and volume anomalies in Polymarket data
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)


class MarketMonitor:
    """Monitors markets for anomalies and significant events"""
    
    def __init__(self, config: Dict[str, Any], database):
        self.config = config
        self.db = database
        
        # Thresholds
        self.price_thresholds = config.get('price_thresholds', {})
        self.volume_thresholds = config.get('volume_thresholds', {})
        
        # Tracking state
        self.price_history: Dict[str, List[Dict]] = defaultdict(list)
        self.volume_history: Dict[str, List[Dict]] = defaultdict(list)
        self.anomaly_cooldown: Dict[str, datetime] = {}
        
        # Moving averages
        self.price_ma_20: Dict[str, float] = {}
        self.volume_ma_20: Dict[str, float] = {}
        
    async def check_anomalies(self) -> List[Dict[str, Any]]:
        """Check all markets for anomalies"""
        anomalies = []
        
        try:
            # Get latest market data
            markets = await self.db.get_latest_market_data()
            
            for market in markets:
                market_id = market['id']
                
                # Skip if in cooldown
                if self._in_cooldown(market_id):
                    continue
                
                # Update history
                self._update_history(market)
                
                # Check for various anomaly types
                price_anomaly = self._check_price_anomaly(market)
                volume_anomaly = self._check_volume_anomaly(market)
                liquidity_anomaly = self._check_liquidity_anomaly(market)
                
                # Combine anomalies
                if price_anomaly or volume_anomaly or liquidity_anomaly:
                    anomaly = self._create_anomaly_record(
                        market,
                        price_anomaly,
                        volume_anomaly,
                        liquidity_anomaly
                    )
                    anomalies.append(anomaly)
                    
                    # Set cooldown
                    self.anomaly_cooldown[market_id] = datetime.utcnow()
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
            return []
    
    def _in_cooldown(self, market_id: str, cooldown_minutes: int = 10) -> bool:
        """Check if market is in cooldown period"""
        if market_id not in self.anomaly_cooldown:
            return False
        
        cooldown_end = self.anomaly_cooldown[market_id] + timedelta(minutes=cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    def _update_history(self, market: Dict[str, Any]):
        """Update price and volume history"""
        market_id = market['id']
        timestamp = datetime.utcnow()
        
        # Update price history
        self.price_history[market_id].append({
            'timestamp': timestamp,
            'price': market['price']
        })
        
        # Update volume history
        self.volume_history[market_id].append({
            'timestamp': timestamp,
            'volume': market['volume'],
            'volume_24h': market.get('volume_24h', market['volume'])
        })
        
        # Keep only last 24 hours
        cutoff = timestamp - timedelta(hours=24)
        self.price_history[market_id] = [
            p for p in self.price_history[market_id]
            if p['timestamp'] > cutoff
        ]
        self.volume_history[market_id] = [
            v for v in self.volume_history[market_id]
            if v['timestamp'] > cutoff
        ]
        
        # Update moving averages
        self._update_moving_averages(market_id)
    
    def _update_moving_averages(self, market_id: str):
        """Calculate moving averages"""
        prices = [p['price'] for p in self.price_history[market_id][-20:]]
        volumes = [v['volume'] for v in self.volume_history[market_id][-20:]]
        
        if len(prices) >= 10:
            self.price_ma_20[market_id] = np.mean(prices)
        
        if len(volumes) >= 10:
            self.volume_ma_20[market_id] = np.mean(volumes)
    
    def _check_price_anomaly(self, market: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for price anomalies"""
        market_id = market['id']
        current_price = market['price']
        
        history = self.price_history[market_id]
        if len(history) < 5:
            return None
        
        anomalies = {}
        
        # Check 5-minute change
        prices_5m = [p['price'] for p in history if p['timestamp'] > datetime.utcnow() - timedelta(minutes=5)]
        if len(prices_5m) >= 2:
            price_5m_ago = prices_5m[0]
            change_5m = abs(current_price - price_5m_ago) / price_5m_ago if price_5m_ago > 0 else 0
            
            threshold_5m = self.price_thresholds.get('spike_5m', 0.05)
            if change_5m >= threshold_5m:
                anomalies['change_5m'] = {
                    'value': current_price - price_5m_ago,
                    'percent': change_5m * 100,
                    'direction': 'up' if current_price > price_5m_ago else 'down'
                }
        
        # Check 1-hour change
        prices_1h = [p['price'] for p in history if p['timestamp'] > datetime.utcnow() - timedelta(hours=1)]
        if len(prices_1h) >= 2:
            price_1h_ago = prices_1h[0]
            change_1h = abs(current_price - price_1h_ago) / price_1h_ago if price_1h_ago > 0 else 0
            
            threshold_1h = self.price_thresholds.get('spike_1h', 0.10)
            if change_1h >= threshold_1h:
                anomalies['change_1h'] = {
                    'value': current_price - price_1h_ago,
                    'percent': change_1h * 100,
                    'direction': 'up' if current_price > price_1h_ago else 'down'
                }
        
        # Check 24-hour change
        if len(history) >= 2:
            price_24h_ago = history[0]['price']
            change_24h = abs(current_price - price_24h_ago) / price_24h_ago if price_24h_ago > 0 else 0
            
            threshold_24h = self.price_thresholds.get('spike_24h', 0.20)
            if change_24h >= threshold_24h:
                anomalies['change_24h'] = {
                    'value': current_price - price_24h_ago,
                    'percent': change_24h * 100,
                    'direction': 'up' if current_price > price_24h_ago else 'down'
                }
        
        # Check volatility (standard deviation)
        if len(history) >= 20:
            recent_prices = [p['price'] for p in history[-20:]]
            volatility = np.std(recent_prices) / np.mean(recent_prices) if np.mean(recent_prices) > 0 else 0
            
            if volatility > 0.05:  # 5% volatility threshold
                anomalies['high_volatility'] = {
                    'value': volatility * 100,
                    'description': 'High price volatility detected'
                }
        
        return anomalies if anomalies else None
    
    def _check_volume_anomaly(self, market: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for volume anomalies"""
        market_id = market['id']
        current_volume = market.get('volume_24h', market['volume'])
        
        history = self.volume_history[market_id]
        if len(history) < 10:
            return None
        
        anomalies = {}
        
        # Calculate average volume
        avg_volume = self.volume_ma_20.get(market_id)
        if avg_volume and avg_volume > 0:
            volume_ratio = current_volume / avg_volume
            threshold = self.volume_thresholds.get('surge_ratio', 3.0)
            
            if volume_ratio >= threshold:
                anomalies['volume_surge'] = {
                    'current': current_volume,
                    'average': avg_volume,
                    'ratio': volume_ratio,
                    'description': f'Volume {volume_ratio:.1f}x above average'
                }
        
        # Check minimum volume threshold
        min_volume = self.volume_thresholds.get('min_volume_usd', 10000)
        if current_volume >= min_volume:
            anomalies['sufficient_liquidity'] = {
                'volume_24h': current_volume,
                'threshold': min_volume
            }
        
        return anomalies if anomalies else None
    
    def _check_liquidity_anomaly(self, market: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for liquidity/order book anomalies"""
        anomalies = {}
        
        # Check spread widening
        spread = market.get('spread', 0)
        best_ask = market.get('best_ask', 0)
        best_bid = market.get('best_bid', 0)
        
        if best_ask > 0 and best_bid > 0:
            spread_pct = spread / ((best_ask + best_bid) / 2)
            
            if spread_pct > 0.02:  # 2% spread
                anomalies['wide_spread'] = {
                    'spread': spread,
                    'spread_percent': spread_pct * 100,
                    'description': 'Wide bid-ask spread detected'
                }
        
        # Check liquidity changes
        liquidity = market.get('liquidity', 0)
        if liquidity < 50000:  # Low liquidity threshold
            anomalies['low_liquidity'] = {
                'liquidity': liquidity,
                'description': 'Low market liquidity'
            }
        
        return anomalies if anomalies else None
    
    def _create_anomaly_record(
        self,
        market: Dict[str, Any],
        price_anomaly: Optional[Dict],
        volume_anomaly: Optional[Dict],
        liquidity_anomaly: Optional[Dict]
    ) -> Dict[str, Any]:
        """Create a standardized anomaly record"""
        
        # Determine primary trigger
        trigger_type = 'unknown'
        severity = 'low'
        
        if price_anomaly:
            if 'change_5m' in price_anomaly:
                change_pct = price_anomaly['change_5m']['percent']
                if change_pct >= 15:
                    trigger_type = 'extreme_price_spike'
                    severity = 'critical'
                elif change_pct >= 10:
                    trigger_type = 'major_price_spike'
                    severity = 'high'
                else:
                    trigger_type = 'price_spike'
                    severity = 'medium'
            elif 'change_1h' in price_anomaly:
                trigger_type = 'price_trend'
                severity = 'medium'
            elif 'high_volatility' in price_anomaly:
                trigger_type = 'volatility_alert'
                severity = 'medium'
        
        if volume_anomaly and 'volume_surge' in volume_anomaly:
            if severity == 'low':
                trigger_type = 'volume_spike'
                severity = 'medium'
        
        return {
            'id': f"anomaly_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{market['id'][:8]}",
            'timestamp': datetime.utcnow().isoformat(),
            'market_id': market['id'],
            'market_slug': market.get('slug', ''),
            'market_question': market['question'],
            'category': market.get('category', 'general'),
            'trigger_type': trigger_type,
            'severity': severity,
            'current_price': market['price'],
            'current_volume': market.get('volume_24h', market['volume']),
            'price_data': price_anomaly or {},
            'volume_data': volume_anomaly or {},
            'liquidity_data': liquidity_anomaly or {},
            'processed': False,
            'signal_generated': False
        }
    
    def get_market_statistics(self, market_id: str) -> Dict[str, Any]:
        """Get statistical analysis for a market"""
        history = self.price_history.get(market_id, [])
        
        if len(history) < 2:
            return {'error': 'Insufficient data'}
        
        prices = [p['price'] for p in history]
        
        return {
            'mean': np.mean(prices),
            'std': np.std(prices),
            'min': np.min(prices),
            'max': np.max(prices),
            'volatility': np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0,
            'data_points': len(prices),
            'time_range_hours': 24
        }
