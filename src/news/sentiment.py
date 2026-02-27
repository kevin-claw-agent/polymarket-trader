"""
Sentiment Analysis Module
Analyzes sentiment of news articles and social media
"""

from typing import Dict, List, Optional, Any
import logging
import re

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes sentiment of text content"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        
        # Initialize sentiment lexicons
        self._init_lexicons()
        
        # Try to load advanced model if available
        self.transformer_model = None
        try:
            from transformers import pipeline
            self.transformer_model = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1  # CPU
            )
            logger.info("Loaded transformer sentiment model")
        except ImportError:
            logger.info("Transformers not available, using lexicon-based analysis")
        except Exception as e:
            logger.warning(f"Could not load transformer model: {e}")
    
    def _init_lexicons(self):
        """Initialize sentiment lexicons"""
        
        # Positive words (financial/prediction context)
        self.positive_words = {
            'surge', 'soar', 'jump', 'rally', 'boom', 'bull', 'bullish', 'gain', 'gains',
            'rise', 'rising', 'up', 'upward', 'higher', 'high', 'strong', 'strength',
            'win', 'wins', 'winning', 'victory', 'success', 'successful', 'breakthrough',
            'approve', 'approved', 'approval', 'pass', 'passed', 'agreement', 'deal',
            'growth', 'growing', 'expand', 'expansion', 'profit', 'profits', 'profitable',
            'recover', 'recovery', 'rebound', 'bounce', 'support', 'momentum', 'optimistic',
            'confident', 'promising', 'excellent', 'outstanding', 'record', 'beat', 'beats',
            'exceed', 'exceeds', 'target', 'upgrade', 'upgraded', 'positive', 'favorable'
        }
        
        # Negative words
        self.negative_words = {
            'crash', 'plunge', 'drop', 'fall', 'fell', 'tumble', 'decline', 'declining',
            'bear', 'bearish', 'loss', 'losses', 'lose', 'losing', 'down', 'downward',
            'lower', 'low', 'weak', 'weakness', 'sell', 'selling', 'dump', 'panic',
            'fail', 'fails', 'failed', 'failure', 'reject', 'rejected', 'rejection',
            'delay', 'delayed', 'postpone', 'cancel', 'cancelled', 'block', 'blocked',
            'ban', 'banned', 'restrict', 'restriction', 'regulation', 'crackdown',
            'fear', 'concern', 'worry', 'worried', 'risk', 'risky', 'uncertain',
            'uncertainty', 'volatile', 'volatility', 'crisis', 'trouble', 'problem',
            'issues', 'bad', 'poor', 'negative', 'unfavorable', 'disappoint', 'disappointed',
            'miss', 'misses', 'cut', 'cuts', 'downgrade', 'downgraded', 'warn', 'warning'
        }
        
        # Intensifiers
        self.intensifiers = {
            'very': 1.5, 'extremely': 2.0, 'incredibly': 2.0, 'remarkably': 1.8,
            'surprisingly': 1.6, 'significantly': 1.7, 'substantially': 1.6,
            'massively': 2.0, 'hugely': 1.9, 'enormously': 2.0, 'tremendously': 1.8,
            'sharply': 1.7, 'steeply': 1.6, 'drastically': 1.9, 'radically': 1.8,
            'slightly': 0.5, 'somewhat': 0.6, 'marginally': 0.4, 'barely': 0.3,
            'hardly': 0.3, 'somewhat': 0.6, 'relatively': 0.7, 'fairly': 0.7
        }
        
        # Negations
        self.negations = {
            'not', "n't", 'no', 'never', 'neither', 'nor', 'hardly', 'scarcely',
            'barely', 'without', 'lack', 'lacking', 'fails', 'failed'
        }
    
    async def analyze(self, news_item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment of a news item"""
        try:
            # Combine title and description for analysis
            text = f"{news_item.get('title', '')} {news_item.get('description', '')}"
            text = text.strip()
            
            if not text:
                return self._empty_sentiment()
            
            # Try transformer model first
            if self.transformer_model:
                transformer_result = self._analyze_transformer(text)
            else:
                transformer_result = None
            
            # Lexicon-based analysis
            lexicon_result = self._analyze_lexicon(text)
            
            # Combine results
            if transformer_result:
                combined = self._combine_sentiments(transformer_result, lexicon_result)
            else:
                combined = lexicon_result
            
            return {
                'news_id': news_item.get('id', ''),
                'text_sample': text[:200],
                'sentiment_score': combined['score'],  # -1 to 1
                'sentiment_label': combined['label'],  # positive, negative, neutral
                'confidence': combined['confidence'],
                'positive_words': lexicon_result.get('positive_words', []),
                'negative_words': lexicon_result.get('negative_words', []),
                'urgency_score': self._calculate_urgency(text),
                'certainty_score': self._calculate_certainty(text),
                'transformer_raw': transformer_result,
                'lexicon_raw': lexicon_result,
                'analyzed_at': self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return self._empty_sentiment()
    
    def _analyze_transformer(self, text: str) -> Dict[str, Any]:
        """Analyze using transformer model"""
        try:
            # Truncate text if too long
            text = text[:512]
            
            result = self.transformer_model(text)[0]
            
            label = result['label'].lower()
            score = result['score']
            
            # Convert to -1 to 1 scale
            if label == 'positive':
                sentiment_score = score
            elif label == 'negative':
                sentiment_score = -score
            else:
                sentiment_score = 0
            
            return {
                'label': label,
                'score': sentiment_score,
                'confidence': score,
                'raw_label': result['label'],
                'raw_score': result['score']
            }
            
        except Exception as e:
            logger.error(f"Transformer analysis error: {e}")
            return None
    
    def _analyze_lexicon(self, text: str) -> Dict[str, Any]:
        """Analyze using lexicon-based approach"""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        pos_count = 0
        neg_count = 0
        pos_words_found = []
        neg_words_found = []
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # Check for negation
            negation = False
            if i > 0 and words[i-1] in self.negations:
                negation = True
            
            # Check for intensifier
            intensifier = 1.0
            if i > 0 and words[i-1] in self.intensifiers:
                intensifier = self.intensifiers[words[i-1]]
            
            # Score word
            if word in self.positive_words:
                if negation:
                    neg_count += intensifier
                    neg_words_found.append(f"not_{word}")
                else:
                    pos_count += intensifier
                    pos_words_found.append(word)
            
            elif word in self.negative_words:
                if negation:
                    pos_count += intensifier
                    pos_words_found.append(f"not_{word}")
                else:
                    neg_count += intensifier
                    neg_words_found.append(word)
            
            i += 1
        
        # Calculate sentiment score
        total = pos_count + neg_count
        if total == 0:
            score = 0
            label = 'neutral'
        else:
            score = (pos_count - neg_count) / total
            if score > 0.2:
                label = 'positive'
            elif score < -0.2:
                label = 'negative'
            else:
                label = 'neutral'
        
        return {
            'label': label,
            'score': score,
            'confidence': min(total / 10, 1.0),  # More words = higher confidence
            'positive_count': pos_count,
            'negative_count': neg_count,
            'positive_words': list(set(pos_words_found)),
            'negative_words': list(set(neg_words_found))
        }
    
    def _combine_sentiments(
        self,
        transformer: Dict[str, Any],
        lexicon: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine transformer and lexicon results"""
        # Weight transformer higher (0.6) vs lexicon (0.4)
        combined_score = 0.6 * transformer['score'] + 0.4 * lexicon['score']
        combined_confidence = 0.6 * transformer['confidence'] + 0.4 * lexicon['confidence']
        
        if combined_score > 0.1:
            label = 'positive'
        elif combined_score < -0.1:
            label = 'negative'
        else:
            label = 'neutral'
        
        return {
            'score': combined_score,
            'label': label,
            'confidence': combined_confidence
        }
    
    def _calculate_urgency(self, text: str) -> float:
        """Calculate urgency score (0-1)"""
        urgency_words = {
            'urgent', 'breaking', 'alert', 'immediate', 'asap', 'now', 'today',
            'just', 'latest', 'update', 'developing', 'happening', 'live'
        }
        
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        urgency_matches = len(words.intersection(urgency_words))
        return min(urgency_matches / 3, 1.0)  # Normalize to 0-1
    
    def _calculate_certainty(self, text: str) -> float:
        """Calculate certainty score (0-1)"""
        certainty_words = {
            'confirmed', 'official', 'announced', 'declared', 'certain',
            'definite', 'clear', 'obvious', 'proven', 'established'
        }
        
        uncertainty_words = {
            'maybe', 'might', 'could', 'possibly', 'perhaps', 'uncertain',
            'unclear', 'rumor', 'speculation', 'allegedly', 'reportedly'
        }
        
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        cert_matches = len(words.intersection(certainty_words))
        uncert_matches = len(words.intersection(uncertainty_words))
        
        if cert_matches + uncert_matches == 0:
            return 0.5  # Neutral
        
        return cert_matches / (cert_matches + uncert_matches)
    
    def _empty_sentiment(self) -> Dict[str, Any]:
        """Return empty sentiment result"""
        return {
            'sentiment_score': 0,
            'sentiment_label': 'neutral',
            'confidence': 0,
            'positive_words': [],
            'negative_words': [],
            'urgency_score': 0,
            'certainty_score': 0.5
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    async def analyze_batch(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze sentiment for a batch of news items"""
        results = []
        for item in news_items:
            result = await self.analyze(item)
            results.append(result)
        return results
    
    def analyze_market_sentiment(
        self,
        news_sentiments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate sentiment for a market from multiple news items"""
        if not news_sentiments:
            return {
                'average_score': 0,
                'sentiment': 'neutral',
                'confidence': 0,
                'news_count': 0
            }
        
        # Calculate weighted average
        total_weight = 0
        weighted_sum = 0
        
        for sentiment in news_sentiments:
            weight = sentiment.get('confidence', 0.5)
            score = sentiment.get('sentiment_score', 0)
            
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight == 0:
            avg_score = 0
        else:
            avg_score = weighted_sum / total_weight
        
        # Determine overall sentiment
        if avg_score > 0.2:
            overall = 'positive'
        elif avg_score < -0.2:
            overall = 'negative'
        else:
            overall = 'neutral'
        
        return {
            'average_score': avg_score,
            'sentiment': overall,
            'confidence': min(total_weight / len(news_sentiments), 1.0),
            'news_count': len(news_sentiments),
            'positive_count': sum(1 for s in news_sentiments if s.get('sentiment_label') == 'positive'),
            'negative_count': sum(1 for s in news_sentiments if s.get('sentiment_label') == 'negative'),
            'neutral_count': sum(1 for s in news_sentiments if s.get('sentiment_label') == 'neutral')
        }
