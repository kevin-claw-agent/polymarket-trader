"""
News Fetcher Module
Fetches news from multiple sources for event correlation
"""

import aiohttp
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import asyncio

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches and aggregates news from multiple sources"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get('newsapi_key')
        self.rss_feeds = config.get('rss_feeds', [])
        self.gdelt_enabled = config.get('gdelt_enabled', False)
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_fetch: Dict[str, datetime] = {}
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'PolymarketTrader/1.0'
                }
            )
        return self.session
    
    async def fetch_latest(self) -> List[Dict[str, Any]]:
        """Fetch latest news from all sources"""
        all_news = []
        
        try:
            # Fetch from NewsAPI
            if self.api_key:
                newsapi_news = await self._fetch_newsapi()
                all_news.extend(newsapi_news)
            
            # Fetch from RSS feeds
            rss_news = await self._fetch_rss_feeds()
            all_news.extend(rss_news)
            
            # Fetch from GDELT if enabled
            if self.gdelt_enabled:
                gdelt_news = await self._fetch_gdelt()
                all_news.extend(gdelt_news)
            
            # Sort by published date
            all_news.sort(key=lambda x: x.get('published', ''), reverse=True)
            
            logger.info(f"Fetched {len(all_news)} news items")
            return all_news
            
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []
    
    async def _fetch_newsapi(self) -> List[Dict[str, Any]]:
        """Fetch news from NewsAPI"""
        try:
            session = await self._get_session()
            
            # Build query for relevant topics
            keywords = [
                'cryptocurrency', 'bitcoin', 'ethereum', 'crypto',
                'election', 'politics', 'voting',
                'sports', 'nba', 'nfl', 'soccer',
                'technology', 'ai', 'tech'
            ]
            
            query = ' OR '.join(keywords)
            from_date = (datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%d')
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'from': from_date,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': 100,
                'apiKey': self.api_key
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = []
                    for article in articles:
                        processed.append({
                            'id': f"newsapi_{hash(article.get('url', ''))}",
                            'source': article.get('source', {}).get('name', 'Unknown'),
                            'title': article.get('title', ''),
                            'description': article.get('description', ''),
                            'content': article.get('content', ''),
                            'url': article.get('url', ''),
                            'published': article.get('publishedAt', ''),
                            'author': article.get('author', ''),
                            'fetched_at': datetime.utcnow().isoformat(),
                            'source_type': 'newsapi'
                        })
                    
                    return processed
                else:
                    logger.warning(f"NewsAPI error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching from NewsAPI: {e}")
            return []
    
    async def _fetch_rss_feeds(self) -> List[Dict[str, Any]]:
        """Fetch news from RSS feeds"""
        all_feeds = []
        
        # Run RSS parsing in thread pool (it's blocking)
        loop = asyncio.get_event_loop()
        
        for feed_url in self.rss_feeds:
            try:
                feed = await loop.run_in_executor(
                    None, 
                    lambda: feedparser.parse(feed_url)
                )
                
                for entry in feed.entries[:20]:  # Limit to 20 per feed
                    # Parse published date
                    published = entry.get('published', '')
                    if not published and 'updated' in entry:
                        published = entry.updated
                    
                    # Check if recent (within 24 hours)
                    try:
                        pub_date = datetime.strptime(published, '%a, %d %b %Y %H:%M:%S %z')
                        if datetime.now(pub_date.tzinfo) - pub_date > timedelta(hours=24):
                            continue
                    except:
                        pass  # Include if can't parse date
                    
                    all_feeds.append({
                        'id': f"rss_{hash(entry.get('link', ''))}",
                        'source': feed.feed.get('title', 'RSS Feed'),
                        'title': entry.get('title', ''),
                        'description': entry.get('summary', ''),
                        'content': entry.get('content', [{}])[0].get('value', '') if entry.get('content') else '',
                        'url': entry.get('link', ''),
                        'published': published,
                        'author': entry.get('author', ''),
                        'fetched_at': datetime.utcnow().isoformat(),
                        'source_type': 'rss'
                    })
                    
            except Exception as e:
                logger.error(f"Error parsing RSS feed {feed_url}: {e}")
        
        return all_feeds
    
    async def _fetch_gdelt(self) -> List[Dict[str, Any]]:
        """Fetch news from GDELT Project"""
        try:
            session = await self._get_session()
            
            # GDELT API endpoint for recent articles
            url = "https://api.gdeltproject.org/api/v2/doc/doc"
            
            # Get articles from last 6 hours
            params = {
                'query': 'politics OR election OR cryptocurrency OR sports',
                'mode': 'ArtList',
                'maxrecords': 50,
                'sort': 'DateDesc',
                'format': 'json'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = []
                    for article in articles:
                        processed.append({
                            'id': f"gdelt_{article.get('id', hash(article.get('url', '')))}",
                            'source': article.get('domain', 'GDELT'),
                            'title': article.get('title', ''),
                            'description': article.get('seendescription', ''),
                            'content': '',
                            'url': article.get('url', ''),
                            'published': article.get('seendate', ''),
                            'author': '',
                            'fetched_at': datetime.utcnow().isoformat(),
                            'source_type': 'gdelt',
                            'tone': article.get('tone', {}),
                            'themes': article.get('themes', [])
                        })
                    
                    return processed
                return []
                
        except Exception as e:
            logger.error(f"Error fetching from GDELT: {e}")
            return []
    
    async def fetch_for_market(self, market_question: str, category: str) -> List[Dict[str, Any]]:
        """Fetch news specifically relevant to a market"""
        try:
            session = await self._get_session()
            
            # Extract keywords from market question
            keywords = self._extract_keywords(market_question, category)
            query = ' AND '.join(keywords[:3])  # Use top 3 keywords
            
            all_news = []
            
            # NewsAPI specific search
            if self.api_key:
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': query,
                    'from': (datetime.utcnow() - timedelta(hours=48)).strftime('%Y-%m-%d'),
                    'sortBy': 'relevancy',
                    'language': 'en',
                    'pageSize': 50,
                    'apiKey': self.api_key
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get('articles', [])
                        
                        for article in articles:
                            all_news.append({
                                'id': f"newsapi_{hash(article.get('url', ''))}",
                                'source': article.get('source', {}).get('name', 'Unknown'),
                                'title': article.get('title', ''),
                                'description': article.get('description', ''),
                                'content': article.get('content', ''),
                                'url': article.get('url', ''),
                                'published': article.get('publishedAt', ''),
                                'fetched_at': datetime.utcnow().isoformat(),
                                'source_type': 'newsapi',
                                'relevance_query': query
                            })
            
            # Score and sort by relevance
            scored_news = self._score_relevance(all_news, market_question, keywords)
            scored_news.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return scored_news[:20]  # Return top 20
            
        except Exception as e:
            logger.error(f"Error fetching market-specific news: {e}")
            return []
    
    def _extract_keywords(self, text: str, category: str) -> List[str]:
        """Extract relevant keywords from text"""
        import re
        
        # Clean and tokenize
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove common stop words
        stop_words = {
            'will', 'by', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'as', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        words = [w for w in text.split() if w not in stop_words and len(w) > 2]
        
        # Add category-specific keywords
        category_keywords = {
            'crypto': ['bitcoin', 'ethereum', 'crypto', 'blockchain', 'btc', 'eth'],
            'politics': ['election', 'vote', 'candidate', 'party', 'poll', 'senate', 'congress'],
            'sports': ['game', 'match', 'team', 'player', 'score', 'win', 'loss'],
            'entertainment': ['movie', 'show', 'award', 'celebrity', 'film']
        }
        
        if category in category_keywords:
            words.extend(category_keywords[category])
        
        # Get unique keywords, prioritize longer words (more specific)
        unique_words = list(set(words))
        unique_words.sort(key=lambda x: len(x), reverse=True)
        
        return unique_words[:10]
    
    def _score_relevance(
        self,
        news_items: List[Dict],
        market_question: str,
        keywords: List[str]
    ) -> List[Dict]:
        """Score news items by relevance to market"""
        market_text = market_question.lower()
        
        for item in news_items:
            title = item.get('title', '').lower()
            desc = item.get('description', '').lower()
            content = item.get('content', '').lower()
            
            score = 0
            
            # Check keyword matches
            for keyword in keywords:
                if keyword in title:
                    score += 3
                if keyword in desc:
                    score += 2
                if keyword in content:
                    score += 1
            
            # Bonus for exact phrase matches
            # Extract key phrases from market question
            phrases = [p.strip() for p in market_text.split('?')[0].split() if len(p) > 4]
            for phrase in phrases[:5]:
                if phrase in title or phrase in desc:
                    score += 2
            
            # Normalize score
            item['relevance_score'] = min(score / len(keywords) if keywords else 0, 1.0)
        
        return news_items
    
    async def close(self):
        """Close connections"""
        if self.session and not self.session.closed:
            await self.session.close()
