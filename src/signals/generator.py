"""
Signal Generator Module
Generates trading signals from overreaction detection results
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import uuid

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trading signals with position sizing and risk parameters"""
    
    def __init__(self, config: Dict[str, Any], database):
        self.config = config.get('generator', {})
        self.db = database
        
        # Signal parameters
        self.min_confidence = self.config.get('min_confidence', 60)
        self.max_daily_signals = self.config.get('max_daily_signals', 10)
        self.cooldown_minutes = self.config.get('cooldown_minutes', 30)
        
        # Position sizing
        self.position_sizing = self.config.get('position_sizing', {})
        self.base_size = self.position_sizing.get('base_size', 0.02)
        self.confidence_multiplier = self.position_sizing.get('confidence_multiplier', 1.5)
        self.max_size = self.position_sizing.get('max_size', 0.05)
        
        # Track signals for cooldown
        self.recent_signals: Dict[str, datetime] = {}
    
    async def generate(
        self,
        anomaly: Dict[str, Any],
        detection: Dict[str, Any],
        related_news: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a trading signal"""
        try:
            # Check daily signal limit
            daily_count = await self.db.get_daily_signal_count()
            if daily_count >= self.max_daily_signals:
                logger.info("Daily signal limit reached")
                return None
            
            # Check cooldown
            market_id = anomaly['market_id']
            if self._in_cooldown(market_id):
                logger.info(f"Market {market_id} in cooldown")
                return None
            
            # Get confidence
            confidence = detection.get('confidence', 0)
            if confidence < self.min_confidence:
                logger.info(f"Confidence {confidence:.1f} below threshold {self.min_confidence}")
                return None
            
            # Determine action
            action = detection.get('recommended_action', 'HOLD')
            if action == 'HOLD':
                return None
            
            # Calculate position size
            position_size = self._calculate_position_size(confidence)
            
            # Calculate entry, stop-loss, and take-profit
            price_levels = self._calculate_price_levels(
                anomaly,
                detection,
                action
            )
            
            # Generate signal ID
            signal_id = f"sig_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Build signal
            signal = {
                'id': signal_id,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'pending',  # pending, approved, rejected, executed, closed
                'market': {
                    'id': market_id,
                    'slug': anomaly.get('market_slug', ''),
                    'question': anomaly.get('market_question', ''),
                    'category': anomaly.get('category', 'general'),
                    'current_price': anomaly.get('current_price', 0)
                },
                'trigger': {
                    'anomaly_id': anomaly.get('id'),
                    'type': anomaly.get('trigger_type'),
                    'severity': anomaly.get('severity'),
                    'price_change_5m': anomaly.get('price_data', {}).get('change_5m', {}),
                    'price_change_1h': anomaly.get('price_data', {}).get('change_1h', {}),
                    'volume_surge': anomaly.get('volume_data', {}).get('volume_surge', {})
                },
                'news': self._format_news(related_news),
                'analysis': {
                    'sentiment_score': detection.get('market_sentiment', {}).get('score', 0),
                    'sentiment_label': detection.get('market_sentiment', {}).get('label', 'neutral'),
                    'divergence_detected': detection.get('divergence', {}).get('detected', False),
                    'divergence_type': detection.get('divergence', {}).get('type', 'none'),
                    'divergence_strength': detection.get('divergence', {}).get('strength', 0),
                    'emotion_type': detection.get('emotion_score', {}).get('type', 'neutral'),
                    'emotion_score': detection.get('emotion_score', {}).get('score', 0),
                    'confidence': confidence,
                    'historical_similar_events': detection.get('historical_comparison', {}).get('similar_events_count', 0),
                    'historical_recovery_rate': detection.get('historical_comparison', {}).get('recovery_rate', 0)
                },
                'signal': {
                    'action': action,
                    'reasoning': detection.get('reasoning', ''),
                    'position_size': position_size,
                    'position_size_percent': f"{position_size * 100:.1f}%",
                    'entry_price': price_levels['entry'],
                    'stop_loss': price_levels['stop_loss'],
                    'take_profit': price_levels['take_profit'],
                    'risk_reward_ratio': price_levels['risk_reward'],
                    'expected_hold_time': self._estimate_hold_time(anomaly, detection)
                },
                'execution': {
                    'approved': False,
                    'approved_by': None,
                    'approved_at': None,
                    'executed_at': None,
                    'executed_price': None,
                    'status': 'pending_approval'
                },
                'performance': {
                    'actual_return': None,
                    'max_drawdown': None,
                    'exit_price': None,
                    'exit_time': None
                }
            }
            
            # Record signal timestamp for cooldown
            self.recent_signals[market_id] = datetime.utcnow()
            
            logger.info(f"Generated signal {signal_id}: {action} {signal['market']['question'][:50]}...")
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return None
    
    def _in_cooldown(self, market_id: str) -> bool:
        """Check if market is in cooldown period"""
        if market_id not in self.recent_signals:
            return False
        
        cooldown_end = self.recent_signals[market_id] + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    def _calculate_position_size(self, confidence: float) -> float:
        """Calculate position size based on confidence"""
        # Base size adjusted by confidence
        confidence_factor = confidence / 100
        adjusted_size = self.base_size * (1 + (confidence_factor * (self.confidence_multiplier - 1)))
        
        # Cap at max size
        return min(adjusted_size, self.max_size)
    
    def _calculate_price_levels(
        self,
        anomaly: Dict,
        detection: Dict,
        action: str
    ) -> Dict[str, Any]:
        """Calculate entry, stop-loss, and take-profit levels"""
        current_price = anomaly.get('current_price', 0.5)
        
        # Get volatility from anomaly
        price_data = anomaly.get('price_data', {})
        change_5m = price_data.get('change_5m', {}).get('percent', 0)
        
        # Set stop-loss based on volatility and action
        if action == 'BUY':
            # For buying, stop-loss below entry
            # More volatile = wider stop
            stop_distance = max(0.05, abs(change_5m) / 100 * 0.5)
            stop_loss = max(0.01, current_price - stop_distance)
            
            # Take profit at 2:1 risk-reward minimum
            risk = current_price - stop_loss
            take_profit = current_price + (risk * 2)
            take_profit = min(take_profit, 0.99)  # Cap at 0.99
            
        else:  # SELL
            # For selling/shorting, stop-loss above entry
            stop_distance = max(0.05, abs(change_5m) / 100 * 0.5)
            stop_loss = min(0.99, current_price + stop_distance)
            
            # Take profit at 2:1 risk-reward
            risk = stop_loss - current_price
            take_profit = current_price - (risk * 2)
            take_profit = max(take_profit, 0.01)  # Floor at 0.01
        
        # Calculate risk-reward ratio
        risk_amount = abs(current_price - stop_loss)
        reward_amount = abs(take_profit - current_price)
        risk_reward = reward_amount / risk_amount if risk_amount > 0 else 0
        
        return {
            'entry': round(current_price, 4),
            'stop_loss': round(stop_loss, 4),
            'take_profit': round(take_profit, 4),
            'risk_reward': round(risk_reward, 2)
        }
    
    def _format_news(self, news_items: List[Dict]) -> List[Dict]:
        """Format news items for signal"""
        formatted = []
        for item in news_items[:5]:  # Top 5 most relevant
            sentiment = item.get('sentiment', {})
            formatted.append({
                'source': item.get('source', 'Unknown'),
                'title': item.get('title', '')[:100],
                'published': item.get('published', ''),
                'sentiment_score': sentiment.get('sentiment_score', 0),
                'sentiment_label': sentiment.get('sentiment_label', 'neutral'),
                'relevance_score': item.get('relevance_score', 0),
                'url': item.get('url', '')
            })
        return formatted
    
    def _estimate_hold_time(
        self,
        anomaly: Dict,
        detection: Dict
    ) -> str:
        """Estimate expected hold time for the trade"""
        category = anomaly.get('category', 'general')
        emotion_type = detection.get('emotion_score', {}).get('type', 'neutral')
        
        # Base estimates by category
        base_times = {
            'crypto': '2-6 hours',
            'politics': '4-12 hours',
            'sports': '1-3 hours',
            'entertainment': '2-4 hours',
            'general': '2-8 hours'
        }
        
        # Adjust for emotion type
        base = base_times.get(category, '2-8 hours')
        
        if emotion_type == 'panic':
            return f"{base} (panic may resolve quickly)"
        elif emotion_type == 'greed':
            return f"{base} (FOMO may fade)"
        else:
            return base
    
    async def approve_signal(self, signal_id: str, approved_by: str) -> bool:
        """Mark a signal as approved for execution"""
        try:
            signal = await self.db.get_signal(signal_id)
            if not signal:
                return False
            
            signal['execution']['approved'] = True
            signal['execution']['approved_by'] = approved_by
            signal['execution']['approved_at'] = datetime.utcnow().isoformat()
            signal['execution']['status'] = 'approved'
            signal['status'] = 'approved'
            
            await self.db.update_signal(signal)
            logger.info(f"Signal {signal_id} approved by {approved_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error approving signal: {e}")
            return False
    
    async def reject_signal(self, signal_id: str, rejected_by: str, reason: str) -> bool:
        """Mark a signal as rejected"""
        try:
            signal = await self.db.get_signal(signal_id)
            if not signal:
                return False
            
            signal['execution']['status'] = 'rejected'
            signal['execution']['rejected_by'] = rejected_by
            signal['execution']['rejection_reason'] = reason
            signal['status'] = 'rejected'
            
            await self.db.update_signal(signal)
            logger.info(f"Signal {signal_id} rejected by {rejected_by}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error rejecting signal: {e}")
            return False
    
    async def execute_signal(self, signal_id: str, executed_price: float) -> bool:
        """Mark a signal as executed"""
        try:
            signal = await self.db.get_signal(signal_id)
            if not signal:
                return False
            
            signal['execution']['executed_at'] = datetime.utcnow().isoformat()
            signal['execution']['executed_price'] = executed_price
            signal['execution']['status'] = 'executed'
            signal['status'] = 'active'
            
            await self.db.update_signal(signal)
            logger.info(f"Signal {signal_id} executed at {executed_price}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return False
    
    async def close_signal(
        self,
        signal_id: str,
        exit_price: float,
        actual_return: float
    ) -> bool:
        """Close a signal with performance data"""
        try:
            signal = await self.db.get_signal(signal_id)
            if not signal:
                return False
            
            signal['performance']['exit_price'] = exit_price
            signal['performance']['exit_time'] = datetime.utcnow().isoformat()
            signal['performance']['actual_return'] = actual_return
            signal['status'] = 'closed'
            signal['execution']['status'] = 'closed'
            
            await self.db.update_signal(signal)
            logger.info(f"Signal {signal_id} closed with return {actual_return:.2%}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing signal: {e}")
            return False
