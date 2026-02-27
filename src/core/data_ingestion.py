"""
Polymarket Data Ingestion Module
Fetches market data from Polymarket CLOB API and blockchain
"""

import asyncio
import aiohttp
import json
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PolymarketDataIngestion:
    """Fetches and processes Polymarket market data"""
    
    def __init__(self, config: Dict[str, Any], database):
        self.config = config
        self.db = database
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_connection = None
        
        self.api_endpoint = config.get('api_endpoint', 'https://clob.polymarket.com')
        self.ws_endpoint = config.get('ws_endpoint', 'wss://ws-subscriber.polymarket.com')
        
        # Cache for market data
        self.market_cache: Dict[str, Dict] = {}
        self.price_history: Dict[str, List[Dict]] = {}
        
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
    
    async def fetch_market_data(self) -> List[Dict[str, Any]]:
        """Fetch all active market data"""
        try:
            session = await self._get_session()
            
            # Fetch markets from CLOB API
            url = f"{self.api_endpoint}/markets"
            params = {
                'active': 'true',
                'closed': 'false',
                'limit': 100
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = data.get('data', [])
                    
                    processed_markets = []
                    for market in markets:
                        processed = self._process_market_data(market)
                        if processed:
                            processed_markets.append(processed)
                            self.market_cache[processed['id']] = processed
                    
                    # Store to database
                    await self.db.store_market_data(processed_markets)
                    
                    logger.debug(f"Fetched {len(processed_markets)} markets")
                    return processed_markets
                else:
                    logger.error(f"API error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []
    
    def _process_market_data(self, market: Dict) -> Optional[Dict[str, Any]]:
        """Process raw market data into standardized format"""
        try:
            market_id = market.get('condition_id') or market.get('id')
            if not market_id:
                return None
            
            # Extract token prices (Yes/No tokens)
            tokens = market.get('tokens', [])
            yes_price = None
            no_price = None
            
            for token in tokens:
                if token.get('outcome') == 'Yes':
                    yes_price = float(token.get('price', 0))
                elif token.get('outcome') == 'No':
                    no_price = float(token.get('price', 0))
            
            # Use mid price if available
            best_ask = float(market.get('best_ask', 0) or 0)
            best_bid = float(market.get('best_bid', 0) or 0)
            
            if yes_price is None and best_ask > 0 and best_bid > 0:
                yes_price = (best_ask + best_bid) / 2
            
            if yes_price is None:
                yes_price = float(market.get('price', 0))
            
            processed = {
                'id': market_id,
                'slug': market.get('market_slug', ''),
                'question': market.get('question', ''),
                'description': market.get('description', ''),
                'category': market.get('category', 'general'),
                'price': yes_price,
                'volume': float(market.get('volume', 0) or 0),
                'liquidity': float(market.get('liquidity', 0) or 0),
                'spread': best_ask - best_bid if best_ask > 0 and best_bid > 0 else 0,
                'best_ask': best_ask,
                'best_bid': best_bid,
                'end_date': market.get('end_date_iso'),
                'resolution_source': market.get('resolution_source', ''),
                'timestamp': datetime.utcnow().isoformat(),
                'raw_data': json.dumps(market)  # Store raw for reference
            }
            
            # Update price history
            if market_id not in self.price_history:
                self.price_history[market_id] = []
            
            self.price_history[market_id].append({
                'timestamp': processed['timestamp'],
                'price': yes_price,
                'volume': processed['volume']
            })
            
            # Keep only last 24 hours of history in memory
            cutoff = datetime.utcnow() - timedelta(hours=24)
            self.price_history[market_id] = [
                p for p in self.price_history[market_id]
                if datetime.fromisoformat(p['timestamp']) > cutoff
            ]
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing market {market.get('id')}: {e}")
            return None
    
    async def fetch_order_book(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Fetch order book for a specific market"""
        try:
            session = await self._get_session()
            url = f"{self.api_endpoint}/book/{market_id}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'market_id': market_id,
                        'bids': data.get('bids', []),
                        'asks': data.get('asks', []),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                return None
        except Exception as e:
            logger.error(f"Error fetching order book for {market_id}: {e}")
            return None
    
    async def fetch_market_history(self, market_id: str, hours: int = 24) -> List[Dict]:
        """Fetch historical price data for a market"""
        try:
            session = await self._get_session()
            
            # Try to get from database first
            history = await self.db.get_price_history(market_id, hours)
            if history:
                return history
            
            # Fallback: return from memory cache
            if market_id in self.price_history:
                return self.price_history[market_id]
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching market history for {market_id}: {e}")
            return []
    
    async def start_websocket(self):
        """Start WebSocket connection for real-time updates"""
        while True:
            try:
                logger.info("Connecting to Polymarket WebSocket...")
                
                async with websockets.connect(self.ws_endpoint) as ws:
                    self.ws_connection = ws
                    
                    # Subscribe to market updates
                    subscribe_msg = {
                        'type': 'subscribe',
                        'channel': 'markets'
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    
                    async for message in ws:
                        await self._handle_ws_message(message)
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect delay
    
    async def _handle_ws_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'price_update':
                await self._handle_price_update(data)
            elif msg_type == 'trade':
                await self._handle_trade(data)
            elif msg_type == 'order_book':
                await self._handle_order_book_update(data)
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _handle_price_update(self, data: Dict):
        """Handle real-time price update"""
        market_id = data.get('market_id')
        new_price = data.get('price')
        
        if market_id and new_price is not None:
            # Update cache
            if market_id in self.market_cache:
                self.market_cache[market_id]['price'] = new_price
                self.market_cache[market_id]['timestamp'] = datetime.utcnow().isoformat()
    
    async def _handle_trade(self, data: Dict):
        """Handle trade notification"""
        # Process trade data for volume tracking
        pass
    
    async def _handle_order_book_update(self, data: Dict):
        """Handle order book update"""
        # Process order book changes
        pass
    
    async def close(self):
        """Close connections"""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.ws_connection:
            await self.ws_connection.close()
