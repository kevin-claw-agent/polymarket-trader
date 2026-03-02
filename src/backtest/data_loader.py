"""
Backtest Data Loader Module
Loads and prepares historical market data for backtesting
"""

import asyncio
import hashlib
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """Loads historical data from Polymarket for backtesting"""
    
    # Target categories for backtesting
    TARGET_CATEGORIES = ['politics', 'finance', 'financial', 'economics', 'business']
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('data', {})
        self.api_endpoint = config.get('api_endpoint', 'https://clob.polymarket.com')
        
        # Data filters
        self.min_liquidity = self.config.get('min_liquidity', 50000)
        self.min_volume = self.config.get('min_volume', 100000)
        self.min_traders = self.config.get('min_traders', 50)
        self.lookback_days = self.config.get('lookback_days', 90)
        
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'PolymarketBacktest/1.0'
                }
            )
        return self.session
    
    async def fetch_markets_for_backtest(
        self,
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets suitable for backtesting
        Filters: high liquidity, high volume, many participants
        """
        try:
            session = await self._get_session()
            
            # Fetch active and recently closed markets
            markets = []
            
            # Fetch active markets
            active_markets = await self._fetch_markets(session, active=True)
            markets.extend(active_markets)
            
            # Fetch recently closed markets for historical data
            closed_markets = await self._fetch_markets(session, active=False, limit=200)
            markets.extend(closed_markets)
            
            # Filter by categories
            if categories is None:
                categories = self.TARGET_CATEGORIES
            
            filtered_markets = self._filter_markets(markets, categories)
            
            logger.info(f"Fetched {len(filtered_markets)} markets for backtest "
                       f"(from {len(markets)} total)")
            
            return filtered_markets
            
        except Exception as e:
            logger.error(f"Error fetching markets for backtest: {e}")
            return []
    
    async def _fetch_markets(
        self,
        session: aiohttp.ClientSession,
        active: bool = True,
        limit: int = 100
    ) -> List[Dict]:
        """Fetch markets from Polymarket API"""
        try:
            url = f"{self.api_endpoint}/markets"
            params = {
                'active': 'true' if active else 'false',
                'closed': 'false' if active else 'true',
                'limit': limit
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    logger.error(f"API error {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def _filter_markets(
        self,
        markets: List[Dict],
        categories: List[str]
    ) -> List[Dict]:
        """Filter markets by category and quality criteria"""
        filtered = []
        
        for market in markets:
            try:
                # Check category
                market_category = market.get('category', '').lower()
                category_match = any(
                    cat.lower() in market_category or market_category in cat.lower()
                    for cat in categories
                )
                
                if not category_match:
                    continue
                
                # Check liquidity
                liquidity = float(market.get('liquidity', 0) or 0)
                if liquidity < self.min_liquidity:
                    continue
                
                # Check volume
                volume = float(market.get('volume', 0) or 0)
                if volume < self.min_volume:
                    continue
                
                # Check participant count (if available)
                trader_count = market.get('trader_count', 0)
                if trader_count and trader_count < self.min_traders:
                    continue
                
                # Process and add market
                processed = self._process_market(market)
                if processed:
                    filtered.append(processed)
                    
            except Exception as e:
                logger.warning(f"Error filtering market: {e}")
                continue
        
        # Sort by volume (highest first)
        filtered.sort(key=lambda x: x['volume'], reverse=True)
        
        return filtered
    
    def _process_market(self, market: Dict) -> Optional[Dict[str, Any]]:
        """Process raw market data"""
        try:
            market_id = market.get('condition_id') or market.get('id')
            if not market_id:
                return None
            
            # Extract prices
            tokens = market.get('tokens', [])
            yes_price = None
            
            for token in tokens:
                if token.get('outcome') == 'Yes':
                    yes_price = float(token.get('price', 0))
                    break
            
            if yes_price is None:
                best_ask = float(market.get('best_ask', 0) or 0)
                best_bid = float(market.get('best_bid', 0) or 0)
                if best_ask > 0 and best_bid > 0:
                    yes_price = (best_ask + best_bid) / 2
                else:
                    yes_price = float(market.get('price', 0.5))
            
            return {
                'id': market_id,
                'slug': market.get('market_slug', ''),
                'question': market.get('question', ''),
                'description': market.get('description', ''),
                'category': market.get('category', 'general'),
                'current_price': yes_price,
                'volume': float(market.get('volume', 0) or 0),
                'liquidity': float(market.get('liquidity', 0) or 0),
                'trader_count': market.get('trader_count', 0),
                'end_date': market.get('end_date_iso'),
                'resolution': market.get('resolution', None),
                'active': market.get('active', True),
                'closed': market.get('closed', False)
            }
            
        except Exception as e:
            logger.error(f"Error processing market: {e}")
            return None
    
    async def fetch_historical_prices(
        self,
        market_id: str,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical price data for a market
        
        This is a simulated implementation - in production, you would:
        - Query your database for stored historical data
        - Or use a data provider API
        """
        try:
            # For backtesting, we simulate historical data
            # In production, replace with actual historical data API
            session = await self._get_session()
            
            # Try to get from API
            url = f"{self.api_endpoint}/markets/{market_id}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    # Generate simulated historical data
                    # In production, this would be real historical data
                    current_price = data.get('price', 0.5)
                    prices = self._generate_simulated_history(
                        market_id, current_price, days
                    )
                    return prices
                else:
                    logger.warning(f"Could not fetch market {market_id}, using simulated history")
                    return self._generate_simulated_history(market_id, 0.5, days)
                    
        except Exception as e:
            logger.error(f"Error fetching historical prices: {e}; using simulated history")
            return self._generate_simulated_history(market_id, 0.5, days)
    
    def _generate_simulated_history(
        self,
        market_id: str,
        end_price: float,
        days: int
    ) -> List[Dict[str, Any]]:
        """
        Generate simulated historical price data
        
        NOTE: This is for demonstration. In production, use real historical data.
        """
        seed = int.from_bytes(hashlib.sha256(market_id.encode('utf-8')).digest()[:4], 'big')
        np.random.seed(seed)
        
        prices = []
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Generate a random walk
        current_price = 0.5  # Start from middle
        
        for i in range(days * 24):  # Hourly data
            timestamp = start_date + timedelta(hours=i)
            
            # Random walk with mean reversion
            change = np.random.normal(0, 0.02)
            
            # Mean reversion towards the end price
            if i > days * 24 * 0.8:
                target = end_price
                current_price = current_price * 0.95 + target * 0.05
            
            current_price = np.clip(current_price + change, 0.01, 0.99)
            
            # Add volume (higher on volatile days)
            volume_base = 50000
            volume = volume_base * (1 + abs(change) * 10)
            
            prices.append({
                'timestamp': timestamp.isoformat(),
                'price': round(current_price, 4),
                'volume': round(volume, 2)
            })
        
        return prices
    
    async def load_backtest_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_markets: int = 50
    ) -> Dict[str, Any]:
        """
        Load complete backtest dataset
        
        Returns:
            Dict with 'markets' and 'price_data' keys
        """
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=self.lookback_days)
        
        logger.info(f"Loading backtest data from {start_date.date()} to {end_date.date()}")
        
        # Fetch markets
        markets = await self.fetch_markets_for_backtest()

        # Network-restricted fallback: generate synthetic but reproducible markets.
        if not markets:
            logger.warning("Falling back to synthetic markets for offline backtest")
            markets = self._generate_fallback_markets(max_markets)
        
        if not markets:
            logger.warning("No markets found for backtest")
            return {'markets': [], 'price_data': {}}
        
        # Limit markets
        markets = markets[:max_markets]
        
        # Fetch historical prices for each market
        price_data = {}
        for market in markets:
            market_id = market['id']
            prices = await self.fetch_historical_prices(market_id, days=self.lookback_days)
            
            if prices:
                # Filter by date range
                filtered_prices = [
                    p for p in prices
                    if start_date <= datetime.fromisoformat(p['timestamp']) <= end_date
                ]
                price_data[market_id] = filtered_prices
            
            await asyncio.sleep(0.1)  # Rate limiting
        
        logger.info(f"Loaded price data for {len(price_data)} markets")
        
        return {
            'markets': markets,
            'price_data': price_data,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }

    def _generate_fallback_markets(self, max_markets: int) -> List[Dict[str, Any]]:
        """Generate deterministic synthetic markets when external API is unavailable."""
        categories = self.config.get('target_categories', self.TARGET_CATEGORIES)
        fallback_count = min(max_markets, 30)
        markets: List[Dict[str, Any]] = []

        for i in range(fallback_count):
            category = categories[i % len(categories)] if categories else 'general'
            markets.append(
                {
                    'id': f'offline_market_{i + 1:03d}',
                    'slug': f'offline-market-{i + 1:03d}',
                    'question': f'Offline synthetic {category} market #{i + 1}',
                    'description': 'Generated market for offline backtest tuning',
                    'category': category,
                    'current_price': 0.5,
                    'volume': float(100000 + i * 5000),
                    'liquidity': float(50000 + i * 2000),
                    'trader_count': 100 + i,
                    'end_date': None,
                    'resolution': None,
                    'active': True,
                    'closed': False,
                }
            )

        return markets
    
    async def close(self):
        """Close connections"""
        if self.session and not self.session.closed:
            await self.session.close()
