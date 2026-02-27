"""
Database Module
Handles all database operations
"""

import asyncpg
import redis.asyncio as redis
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL and Redis database handler"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pg_config = config.get('postgres', {})
        self.redis_config = config.get('redis', {})
        
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Establish database connections"""
        try:
            # PostgreSQL
            self.pg_pool = await asyncpg.create_pool(
                host=self.pg_config.get('host', 'localhost'),
                port=self.pg_config.get('port', 5432),
                database=self.pg_config.get('database', 'polymarket_trader'),
                user=self.pg_config.get('user', 'postgres'),
                password=self.pg_config.get('password', ''),
                min_size=5,
                max_size=20
            )
            
            # Create tables if not exist
            await self._create_tables()
            
            logger.info("PostgreSQL connected")
            
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            # Fallback to SQLite for development
            logger.info("Falling back to SQLite for development")
            await self._init_sqlite()
        
        try:
            # Redis
            self.redis_client = redis.Redis(
                host=self.redis_config.get('host', 'localhost'),
                port=self.redis_config.get('port', 6379),
                db=self.redis_config.get('db', 0),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connected")
            
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None
    
    async def _create_tables(self):
        """Create database tables"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            # Markets table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS markets (
                    id TEXT PRIMARY KEY,
                    slug TEXT,
                    question TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    price REAL,
                    volume REAL,
                    liquidity REAL,
                    spread REAL,
                    best_ask REAL,
                    best_bid REAL,
                    end_date TIMESTAMP,
                    resolution_source TEXT,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    raw_data JSONB
                )
            """)
            
            # Price history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id SERIAL PRIMARY KEY,
                    market_id TEXT REFERENCES markets(id),
                    price REAL NOT NULL,
                    volume REAL,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Anomalies table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    market_id TEXT REFERENCES markets(id),
                    market_slug TEXT,
                    market_question TEXT,
                    category TEXT,
                    trigger_type TEXT,
                    severity TEXT,
                    current_price REAL,
                    current_volume REAL,
                    price_data JSONB,
                    volume_data JSONB,
                    liquidity_data JSONB,
                    processed BOOLEAN DEFAULT FALSE,
                    signal_generated BOOLEAN DEFAULT FALSE
                )
            """)
            
            # News table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    title TEXT,
                    description TEXT,
                    content TEXT,
                    url TEXT,
                    published TIMESTAMP,
                    author TEXT,
                    fetched_at TIMESTAMP DEFAULT NOW(),
                    source_type TEXT,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    urgency_score REAL,
                    relevance_score REAL,
                    related_market_ids TEXT[]
                )
            """)
            
            # Signals table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    status TEXT DEFAULT 'pending',
                    market_id TEXT,
                    market_slug TEXT,
                    market_question TEXT,
                    category TEXT,
                    current_price REAL,
                    trigger_anomaly_id TEXT,
                    trigger_type TEXT,
                    trigger_severity TEXT,
                    action TEXT,
                    confidence REAL,
                    position_size REAL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    risk_reward_ratio REAL,
                    reasoning TEXT,
                    expected_hold_time TEXT,
                    approved BOOLEAN DEFAULT FALSE,
                    approved_by TEXT,
                    approved_at TIMESTAMP,
                    executed_at TIMESTAMP,
                    executed_price REAL,
                    exit_price REAL,
                    exit_time TIMESTAMP,
                    actual_return REAL,
                    max_drawdown REAL,
                    signal_data JSONB
                )
            """)
            
            # Trades table (for tracking executed trades)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    signal_id TEXT REFERENCES signals(id),
                    market_id TEXT,
                    action TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    position_size REAL,
                    entry_time TIMESTAMP,
                    exit_time TIMESTAMP,
                    pnl REAL,
                    exit_reason TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Risk events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    event_type TEXT,
                    market_id TEXT,
                    details JSONB
                )
            """)
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_price_history_market ON price_history(market_id, timestamp)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_news_published ON news(published)")
            
            logger.info("Database tables created")
    
    async def _init_sqlite(self):
        """Initialize SQLite fallback for development"""
        import aiosqlite
        self.sqlite_db = await aiosqlite.connect('polymarket_trader.db')
        self.using_sqlite = True
        logger.info("SQLite initialized for development")
    
    # Market data operations
    async def store_market_data(self, markets: List[Dict]):
        """Store market data"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            for market in markets:
                await conn.execute("""
                    INSERT INTO markets (id, slug, question, description, category, 
                        price, volume, liquidity, spread, best_ask, best_bid, 
                        end_date, resolution_source, raw_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (id) DO UPDATE SET
                        price = EXCLUDED.price,
                        volume = EXCLUDED.volume,
                        liquidity = EXCLUDED.liquidity,
                        spread = EXCLUDED.spread,
                        best_ask = EXCLUDED.best_ask,
                        best_bid = EXCLUDED.best_bid,
                        updated_at = NOW()
                """, 
                market['id'], market.get('slug'), market['question'],
                market.get('description'), market.get('category'),
                market['price'], market['volume'], market.get('liquidity'),
                market.get('spread'), market.get('best_ask'), market.get('best_bid'),
                market.get('end_date'), market.get('resolution_source'),
                json.dumps(market.get('raw_data'))
                )
    
    async def get_latest_market_data(self) -> List[Dict]:
        """Get latest market data"""
        if not self.pg_pool:
            return []
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM markets WHERE updated_at > NOW() - INTERVAL '1 hour'")
            return [dict(row) for row in rows]
    
    async def get_price_history(self, market_id: str, hours: int = 24) -> List[Dict]:
        """Get price history for a market"""
        if not self.pg_pool:
            return []
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM price_history 
                WHERE market_id = $1 AND timestamp > NOW() - INTERVAL '$2 hours'
                ORDER BY timestamp
            """, market_id, hours)
            return [dict(row) for row in rows]
    
    # Anomaly operations
    async def store_anomaly(self, anomaly: Dict):
        """Store anomaly detection"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO anomalies (id, timestamp, market_id, market_slug, 
                    market_question, category, trigger_type, severity, current_price,
                    current_volume, price_data, volume_data, liquidity_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (id) DO NOTHING
            """,
            anomaly['id'], anomaly['timestamp'], anomaly['market_id'],
            anomaly.get('market_slug'), anomaly.get('market_question'),
            anomaly.get('category'), anomaly['trigger_type'], anomaly['severity'],
            anomaly['current_price'], anomaly['current_volume'],
            json.dumps(anomaly.get('price_data')),
            json.dumps(anomaly.get('volume_data')),
            json.dumps(anomaly.get('liquidity_data'))
            )
    
    async def get_unprocessed_anomalies(self) -> List[Dict]:
        """Get anomalies that haven't been processed into signals"""
        if not self.pg_pool:
            return []
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM anomalies 
                WHERE processed = FALSE AND timestamp > NOW() - INTERVAL '1 hour'
                ORDER BY timestamp DESC
            """)
            return [dict(row) for row in rows]
    
    async def get_historical_anomalies(self, market_id: str, days: int = 30) -> List[Dict]:
        """Get historical anomalies for a market"""
        if not self.pg_pool:
            return []
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM anomalies 
                WHERE market_id = $1 AND timestamp > NOW() - INTERVAL '$2 days'
                ORDER BY timestamp DESC
            """, market_id, days)
            return [dict(row) for row in rows]
    
    # News operations
    async def store_news(self, news_item: Dict, sentiment: Dict):
        """Store news item with sentiment"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO news (id, source, title, description, content, url,
                    published, author, fetched_at, source_type, sentiment_score,
                    sentiment_label, urgency_score, relevance_score)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (id) DO UPDATE SET
                    relevance_score = EXCLUDED.relevance_score
            """,
            news_item['id'], news_item.get('source'), news_item.get('title'),
            news_item.get('description'), news_item.get('content'), news_item.get('url'),
            news_item.get('published'), news_item.get('author'),
            news_item.get('fetched_at'), news_item.get('source_type'),
            sentiment.get('sentiment_score'), sentiment.get('sentiment_label'),
            sentiment.get('urgency_score'), news_item.get('relevance_score', 0)
            )
    
    async def get_related_news(self, market_id: str, hours: int = 1) -> List[Dict]:
        """Get news related to a market"""
        if not self.pg_pool:
            return []
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM news 
                WHERE fetched_at > NOW() - INTERVAL '$2 hours'
                AND (related_market_ids @> ARRAY[$1] OR related_market_ids IS NULL)
                ORDER BY relevance_score DESC, fetched_at DESC
                LIMIT 20
            """, market_id, hours)
            return [dict(row) for row in rows]
    
    # Signal operations
    async def store_signal(self, signal: Dict):
        """Store trading signal"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO signals (id, timestamp, status, market_id, market_slug,
                    market_question, category, current_price, trigger_anomaly_id,
                    trigger_type, trigger_severity, action, confidence, position_size,
                    entry_price, stop_loss, take_profit, risk_reward_ratio, reasoning,
                    expected_hold_time, signal_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
            """,
            signal['id'], signal['timestamp'], signal['status'],
            signal['market']['id'], signal['market'].get('slug'),
            signal['market']['question'], signal['market'].get('category'),
            signal['market']['current_price'], signal['trigger'].get('anomaly_id'),
            signal['trigger'].get('type'), signal['trigger'].get('severity'),
            signal['signal']['action'], signal['analysis']['confidence'],
            signal['signal']['position_size'], signal['signal']['entry_price'],
            signal['signal']['stop_loss'], signal['signal']['take_profit'],
            signal['signal']['risk_reward_ratio'], signal['signal']['reasoning'],
            signal['signal']['expected_hold_time'], json.dumps(signal)
            )
    
    async def get_signal(self, signal_id: str) -> Optional[Dict]:
        """Get signal by ID"""
        if not self.pg_pool:
            return None
        
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM signals WHERE id = $1", signal_id)
            return dict(row) if row else None
    
    async def update_signal(self, signal: Dict):
        """Update signal status"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                UPDATE signals SET
                    status = $2,
                    approved = $3,
                    approved_by = $4,
                    approved_at = $5,
                    executed_at = $6,
                    executed_price = $7,
                    exit_price = $8,
                    exit_time = $9,
                    actual_return = $10,
                    max_drawdown = $11
                WHERE id = $1
            """,
            signal['id'], signal['status'], signal['execution'].get('approved'),
            signal['execution'].get('approved_by'), signal['execution'].get('approved_at'),
            signal['execution'].get('executed_at'), signal['execution'].get('executed_price'),
            signal['performance'].get('exit_price'), signal['performance'].get('exit_time'),
            signal['performance'].get('actual_return'), signal['performance'].get('max_drawdown')
            )
    
    async def get_daily_signal_count(self) -> int:
        """Get count of signals generated today"""
        if not self.pg_pool:
            return 0
        
        async with self.pg_pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM signals 
                WHERE timestamp > DATE_TRUNC('day', NOW())
            """)
            return count or 0
    
    # Risk operations
    async def get_market_exposure(self, market_id: str) -> float:
        """Get current exposure for a market"""
        if not self.pg_pool:
            return 0
        
        async with self.pg_pool.acquire() as conn:
            exposure = await conn.fetchval("""
                SELECT COALESCE(SUM(position_size), 0) FROM signals 
                WHERE market_id = $1 AND status IN ('active', 'approved')
            """, market_id)
            return exposure or 0
    
    async def get_total_exposure(self) -> float:
        """Get total exposure across all markets"""
        if not self.pg_pool:
            return 0
        
        async with self.pg_pool.acquire() as conn:
            exposure = await conn.fetchval("""
                SELECT COALESCE(SUM(position_size), 0) FROM signals 
                WHERE status IN ('active', 'approved')
            """)
            return exposure or 0
    
    async def get_correlated_exposure(self, correlation_group: str) -> float:
        """Get exposure for correlated markets"""
        # Simplified - would need market categorization
        return await self.get_total_exposure()
    
    async def get_daily_pnl(self) -> float:
        """Get daily PnL"""
        if not self.pg_pool:
            return 0
        
        async with self.pg_pool.acquire() as conn:
            pnl = await conn.fetchval("""
                SELECT COALESCE(SUM(actual_return * position_size), 0) FROM signals 
                WHERE exit_time > DATE_TRUNC('day', NOW())
            """)
            return pnl or 0
    
    async def get_weekly_pnl(self) -> float:
        """Get weekly PnL"""
        if not self.pg_pool:
            return 0
        
        async with self.pg_pool.acquire() as conn:
            pnl = await conn.fetchval("""
                SELECT COALESCE(SUM(actual_return * position_size), 0) FROM signals 
                WHERE exit_time > DATE_TRUNC('week', NOW())
            """)
            return pnl or 0
    
    async def get_open_positions_count(self) -> int:
        """Get count of open positions"""
        if not self.pg_pool:
            return 0
        
        async with self.pg_pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM signals WHERE status = 'active'
            """)
            return count or 0
    
    async def log_circuit_breaker(self, event: Dict):
        """Log circuit breaker event"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO risk_events (timestamp, event_type, market_id, details)
                VALUES ($1, $2, $3, $4)
            """,
            event['timestamp'], 'circuit_breaker', event.get('market_id'),
            json.dumps(event)
            )
    
    async def log_trade_close(self, trade: Dict):
        """Log trade close"""
        if not self.pg_pool:
            return
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO trades (signal_id, market_id, action, exit_price, pnl, exit_reason, exit_time)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            trade['signal_id'], trade.get('market_id'), trade.get('action'),
            trade['exit_price'], trade['pnl'], trade['reason'], trade['timestamp']
            )
    
    async def update_position_pnl(self, signal_id: str, pnl: float):
        """Update running PnL for a position"""
        if not self.pg_pool:
            return
        
        # Could store in Redis for real-time updates
        if self.redis_client:
            await self.redis_client.setex(f"pnl:{signal_id}", 3600, str(pnl))
    
    async def close(self):
        """Close database connections"""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Database connections closed")
