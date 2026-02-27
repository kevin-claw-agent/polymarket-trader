"""
Overreaction Detection Module
Detects when markets are overreacting to news/events
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import numpy as np

logger = logging.getLogger(__name__)


class OverreactionDetector:
    """Detects market overreactions to events"""
    
    def __init__(self, config: Dict[str, Any], database):
        self.config = config.get('detection', {})
        self.db = database
        
        # Thresholds
        self.sentiment_divergence_threshold = self.config.get('sentiment_divergence_threshold', 0.5)
        self.panic_threshold = self.config.get('panic_threshold', 70)
        self.greed_threshold = self.config.get('greed_threshold', 70)
        
        # Historical comparison
        self.lookback_periods = self.config.get('lookback_periods', 30)
        self.similarity_threshold = self.config.get('similarity_threshold', 0.8)
    
    async def detect(
        self,
        anomaly: Dict[str, Any],
        related_news: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect if market is overreacting"""
        try:
            market_id = anomaly['market_id']
            
            # Get market sentiment from news
            market_sentiment = self._calculate_market_sentiment(related_news)
            
            # Get price movement
            price_movement = self._extract_price_movement(anomaly)
            
            # Check for sentiment-price divergence
            divergence = self._check_divergence(market_sentiment, price_movement)
            
            # Calculate panic/greed score
            emotion_score = self._calculate_emotion_score(anomaly, price_movement)
            
            # Compare with historical similar events
            historical_comparison = await self._compare_historical(market_id, anomaly)
            
            # Calculate overreaction score
            overreaction_score = self._calculate_overreaction_score(
                divergence,
                emotion_score,
                historical_comparison
            )
            
            # Determine if overreaction
            is_overreaction = overreaction_score >= 60
            
            return {
                'is_overreaction': is_overreaction,
                'confidence': overreaction_score,
                'market_sentiment': market_sentiment,
                'price_movement': price_movement,
                'divergence': divergence,
                'emotion_score': emotion_score,
                'historical_comparison': historical_comparison,
                'reasoning': self._generate_reasoning(
                    divergence,
                    emotion_score,
                    historical_comparison
                ),
                'recommended_action': self._recommend_action(
                    price_movement,
                    divergence
                )
            }
            
        except Exception as e:
            logger.error(f"Error in overreaction detection: {e}")
            return {'is_overreaction': False, 'confidence': 0}
    
    def _calculate_market_sentiment(self, news_items: List[Dict]) -> Dict[str, Any]:
        """Calculate aggregated sentiment from news"""
        if not news_items:
            return {
                'score': 0,
                'label': 'neutral',
                'confidence': 0,
                'urgency': 0
            }
        
        sentiments = []
        for item in news_items:
            sentiment = item.get('sentiment', {})
            sentiments.append({
                'score': sentiment.get('sentiment_score', 0),
                'confidence': sentiment.get('confidence', 0.5),
                'urgency': sentiment.get('urgency_score', 0)
            })
        
        # Weight by confidence
        total_weight = sum(s['confidence'] for s in sentiments)
        if total_weight == 0:
            avg_score = 0
        else:
            avg_score = sum(s['score'] * s['confidence'] for s in sentiments) / total_weight
        
        avg_urgency = sum(s['urgency'] for s in sentiments) / len(sentiments)
        
        if avg_score > 0.2:
            label = 'positive'
        elif avg_score < -0.2:
            label = 'negative'
        else:
            label = 'neutral'
        
        return {
            'score': avg_score,
            'label': label,
            'confidence': min(total_weight / len(sentiments), 1.0),
            'urgency': avg_urgency,
            'news_count': len(news_items)
        }
    
    def _extract_price_movement(self, anomaly: Dict) -> Dict[str, Any]:
        """Extract price movement data from anomaly"""
        price_data = anomaly.get('price_data', {})
        
        # Get the most significant price change
        change_5m = price_data.get('change_5m', {})
        change_1h = price_data.get('change_1h', {})
        
        if change_5m.get('percent', 0) >= change_1h.get('percent', 0):
            primary_change = change_5m
            timeframe = '5m'
        else:
            primary_change = change_1h
            timeframe = '1h'
        
        return {
            'percent': primary_change.get('percent', 0),
            'direction': primary_change.get('direction', 'neutral'),
            'absolute_change': primary_change.get('value', 0),
            'timeframe': timeframe,
            'current_price': anomaly.get('current_price', 0)
        }
    
    def _check_divergence(
        self,
        sentiment: Dict[str, Any],
        price_movement: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check for sentiment-price divergence"""
        sentiment_score = sentiment['score']
        price_direction = price_movement['direction']
        price_change = price_movement['percent']
        
        # Determine expected price direction from sentiment
        if sentiment_score > 0.3:
            expected_direction = 'up'
        elif sentiment_score < -0.3:
            expected_direction = 'down'
        else:
            expected_direction = 'neutral'
        
        # Check for divergence
        divergence_detected = False
        divergence_strength = 0
        
        if expected_direction == 'up' and price_direction == 'down':
            # Sentiment positive but price dropping = potential oversold
            divergence_detected = True
            divergence_strength = abs(sentiment_score) + (price_change / 100)
            divergence_type = 'oversold'
            
        elif expected_direction == 'down' and price_direction == 'up':
            # Sentiment negative but price rising = potential overbought
            divergence_detected = True
            divergence_strength = abs(sentiment_score) + (price_change / 100)
            divergence_type = 'overbought'
            
        elif expected_direction == 'neutral':
            # Neutral sentiment but significant price move = possible overreaction
            if price_change > 10:
                divergence_detected = True
                divergence_strength = price_change / 100
                divergence_type = 'neutral_sentiment_extreme_move'
            else:
                divergence_type = 'none'
        else:
            divergence_type = 'aligned'
        
        return {
            'detected': divergence_detected,
            'strength': min(divergence_strength, 1.0),
            'type': divergence_type,
            'sentiment_direction': expected_direction,
            'price_direction': price_direction,
            'sentiment_score': sentiment_score,
            'price_change': price_change
        }
    
    def _calculate_emotion_score(
        self,
        anomaly: Dict,
        price_movement: Dict
    ) -> Dict[str, Any]:
        """Calculate panic/greed emotion score"""
        price_change = price_movement['percent']
        direction = price_movement['direction']
        
        # Volume data
        volume_data = anomaly.get('volume_data', {})
        volume_surge = volume_data.get('volume_surge', {}).get('ratio', 1.0)
        
        # Base emotion score on price change magnitude
        base_score = min(price_change * 2, 100)  # Scale up, cap at 100
        
        # Adjust for volume (higher volume = stronger emotion)
        volume_multiplier = min(volume_surge / 3, 2.0)
        adjusted_score = base_score * volume_multiplier
        
        # Determine emotion type
        if direction == 'down':
            emotion_type = 'panic'
            emotion_label = 'Panic Selling'
        elif direction == 'up':
            emotion_type = 'greed'
            emotion_label = 'FOMO Buying'
        else:
            emotion_type = 'neutral'
            emotion_label = 'Neutral'
        
        return {
            'score': min(adjusted_score, 100),
            'type': emotion_type,
            'label': emotion_label,
            'is_extreme': adjusted_score >= self.panic_threshold,
            'components': {
                'price_change_contribution': base_score,
                'volume_multiplier': volume_multiplier
            }
        }
    
    async def _compare_historical(
        self,
        market_id: str,
        current_anomaly: Dict
    ) -> Dict[str, Any]:
        """Compare with historical similar events"""
        try:
            # Get historical anomalies for this market
            historical = await self.db.get_historical_anomalies(
                market_id,
                days=self.lookback_periods
            )
            
            if not historical:
                return {
                    'similar_events_count': 0,
                    'average_recovery': None,
                    'similarity_score': 0
                }
            
            # Current event characteristics
            current_price_change = current_anomaly.get('price_data', {}).get('change_5m', {}).get('percent', 0)
            current_category = current_anomaly.get('category', 'general')
            
            similar_events = []
            recoveries = []
            
            for event in historical:
                event_change = event.get('price_data', {}).get('change_5m', {}).get('percent', 0)
                event_category = event.get('category', 'general')
                
                # Check similarity
                price_similarity = 1 - abs(current_price_change - event_change) / max(abs(current_price_change), 1)
                category_match = 1 if current_category == event_category else 0.5
                
                similarity = (price_similarity * 0.7) + (category_match * 0.3)
                
                if similarity >= self.similarity_threshold:
                    similar_events.append(event)
                    
                    # Check if there was a recovery
                    if event.get('recovery_data'):
                        recoveries.append(event['recovery_data'].get('percent', 0))
            
            avg_recovery = np.mean(recoveries) if recoveries else None
            
            return {
                'similar_events_count': len(similar_events),
                'average_recovery_percent': avg_recovery,
                'similarity_score': len(similar_events) / len(historical) if historical else 0,
                'recovery_rate': len([r for r in recoveries if r > 0]) / len(recoveries) if recoveries else 0
            }
            
        except Exception as e:
            logger.error(f"Error comparing historical events: {e}")
            return {
                'similar_events_count': 0,
                'average_recovery': None,
                'similarity_score': 0
            }
    
    def _calculate_overreaction_score(
        self,
        divergence: Dict,
        emotion_score: Dict,
        historical: Dict
    ) -> float:
        """Calculate overall overreaction confidence score (0-100)"""
        score = 0
        
        # Divergence contribution (40%)
        if divergence['detected']:
            score += 40 * divergence['strength']
        
        # Emotion contribution (35%)
        if emotion_score['is_extreme']:
            score += 35 * (emotion_score['score'] / 100)
        else:
            score += 20 * (emotion_score['score'] / 100)
        
        # Historical similarity contribution (25%)
        if historical['similar_events_count'] > 0:
            if historical.get('recovery_rate', 0) > 0.5:
                score += 25 * historical['similarity_score']
        
        return min(score, 100)
    
    def _generate_reasoning(
        self,
        divergence: Dict,
        emotion_score: Dict,
        historical: Dict
    ) -> str:
        """Generate human-readable reasoning"""
        reasons = []
        
        if divergence['detected']:
            reasons.append(
                f"{divergence['type'].replace('_', ' ').title()}: "
                f"News sentiment is {divergence['sentiment_direction']} "
                f"but price moved {divergence['price_direction']} by {divergence['price_change']:.1f}%"
            )
        
        if emotion_score['is_extreme']:
            reasons.append(
                f"{emotion_score['label']} detected (score: {emotion_score['score']:.1f})"
            )
        
        if historical['similar_events_count'] > 0:
            recovery_info = ""
            if historical.get('recovery_rate'):
                recovery_info = f" with {historical['recovery_rate']*100:.0f}% recovery rate"
            reasons.append(
                f"Similar to {historical['similar_events_count']} historical events{recovery_info}"
            )
        
        return "; ".join(reasons) if reasons else "No clear overreaction indicators"
    
    def _recommend_action(
        self,
        price_movement: Dict,
        divergence: Dict
    ) -> str:
        """Recommend trading action based on analysis"""
        if not divergence['detected']:
            return 'HOLD'
        
        direction = price_movement['direction']
        div_type = divergence['type']
        
        if div_type == 'oversold' or (direction == 'down' and divergence['detected']):
            return 'BUY'  # Market over-panicking, buy the dip
        elif div_type == 'overbought' or (direction == 'up' and divergence['detected']):
            return 'SELL'  # Market FOMOing, time to sell/short
        else:
            return 'HOLD'
