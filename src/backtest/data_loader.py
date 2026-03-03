"""
Backtest Data Loader Module
Loads and prepares historical market data for backtesting
"""

import asyncio
import hashlib
import aiohttp
import json
import os
import time
import socket
from datetime import datetime, timedelta, timezone
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
        self.api_endpoint = self.config.get('api_endpoint', config.get('api_endpoint', 'https://clob.polymarket.com'))
        
        # Data filters
        self.min_liquidity = self.config.get('min_liquidity', 50000)
        self.min_volume = self.config.get('min_volume', 100000)
        self.min_traders = self.config.get('min_traders', 50)
        self.lookback_days = self.config.get('lookback_days', 90)
        self.request_interval_seconds = float(self.config.get('request_interval_seconds', 0.2))
        self.max_retries = int(self.config.get('max_retries', 4))
        self.retry_backoff_seconds = float(self.config.get('retry_backoff_seconds', 0.8))
        self.cache_dir = self.config.get('cache_dir', 'backtest_data_cache')
        self.history_interval = self.config.get('history_interval', '1h')
        self.history_chunk_days = int(self.config.get('history_chunk_days', 14))
        self.use_simulated_history = bool(self.config.get('use_simulated_history', False))
        self.enable_generated_fallback = bool(self.config.get('enable_generated_fallback', False))
        self.exclude_closed_markets = bool(self.config.get('exclude_closed_markets', True))
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_ts = 0.0
        self._request_lock = asyncio.Lock()
        os.makedirs(self.cache_dir, exist_ok=True)

        self.run_summary: Dict[str, Any] = {
            'api_endpoint': self.api_endpoint,
            'network': {'status': 'unknown', 'detail': ''},
            'markets': {'requested': 0, 'real_fetched': 0, 'fallback_generated': 0, 'selected': 0, 'closed_excluded': 0, 'out_of_window_excluded': 0},
            'history': {'markets_with_prices': 0, 'cache_hits': 0, 'api_downloads': 0, 'simulated_used': 0, 'failed': 0, 'history_empty_count': 0, 'date_filtered_out_count': 0},
        }
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(
                connector=connector,
                trust_env=True,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'PolymarketBacktest/1.0'
                }
            )
        return self.session
    
    async def check_network_connectivity(self) -> Dict[str, str]:
        """Lightweight network check for the configured API host."""
        host = self.api_endpoint.replace('https://', '').replace('http://', '').split('/')[0]
        proxy_enabled = any(os.environ.get(k) for k in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy'))
        result = {'status': 'ok', 'detail': ''}
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            ipv4 = [i for i in infos if i[0] == socket.AF_INET]
            if not ipv4:
                result = {'status': 'warning', 'detail': f'No IPv4 address resolved for {host}'}
            else:
                via = 'proxy-enabled environment' if proxy_enabled else 'direct network'
                result = {'status': 'ok', 'detail': f'Resolved {host} to {len(ipv4)} IPv4 address(es) ({via})'}
        except Exception as e:
            result = {'status': 'error', 'detail': f'DNS/connectivity check failed for {host}: {e}'}

        self.run_summary['network'] = result
        if result['status'] != 'ok':
            logger.warning('Network check: %s', result['detail'])
        else:
            logger.info('Network check: %s', result['detail'])
        return result

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
            await self.check_network_connectivity()
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
            
            filtered_markets = self._filter_markets(markets, categories, exclude_closed=self.exclude_closed_markets)

            # If strict closed-market exclusion yields nothing, auto-relax to recover usable history datasets.
            if not filtered_markets and self.exclude_closed_markets:
                logger.warning("No markets after excluding closed markets; retrying with closed markets included")
                filtered_markets = self._filter_markets(markets, categories, exclude_closed=False)

            self.run_summary['markets']['real_fetched'] = len(filtered_markets)
            
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
            
            data = await self._request_json(url, params=params)
            if data:
                return data.get('data', [])
            return []
                    
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    async def _request_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """HTTP GET with retry/backoff and global rate limiting."""
        session = await self._get_session()

        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._request_lock:
                    wait_s = self.request_interval_seconds - (time.monotonic() - self._last_request_ts)
                    if wait_s > 0:
                        await asyncio.sleep(wait_s)

                    async with session.get(url, params=params) as response:
                        self._last_request_ts = time.monotonic()

                        if response.status == 200:
                            return await response.json()

                        body = await response.text()
                        logger.warning(
                            "Request failed (%s) %s params=%s body=%s",
                            response.status,
                            url,
                            params,
                            body[:200],
                        )

                        if response.status not in {408, 409, 425, 429, 500, 502, 503, 504}:
                            return None
            except Exception as e:
                logger.warning("Request error on attempt %s/%s for %s: %s", attempt, self.max_retries, url, e)

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_backoff_seconds * attempt)

        return None
    
    def _filter_markets(
        self,
        markets: List[Dict],
        categories: List[str],
        exclude_closed: Optional[bool] = None
    ) -> List[Dict]:
        """Filter markets by category and quality criteria"""
        filtered = []
        if exclude_closed is None:
            exclude_closed = self.exclude_closed_markets

        for market in markets:
            try:
                if exclude_closed and bool(market.get('closed')):
                    self.run_summary['markets']['closed_excluded'] += 1
                    continue

                # Check category (API often has empty `category`; fallback to tags/event/question text)
                tags = market.get('tags') or []
                events = market.get('events') or []
                event_slugs = [e.get('slug', '') for e in events if isinstance(e, dict)]
                text_fields = [
                    str(market.get('category', '') or ''),
                    str(market.get('question', '') or ''),
                    str(market.get('description', '') or ''),
                    str(market.get('market_slug', '') or ''),
                    ' '.join(str(t) for t in tags),
                    ' '.join(str(es) for es in event_slugs),
                ]
                searchable = ' '.join(text_fields).lower()
                category_match = any(cat.lower() in searchable for cat in categories)

                if not category_match:
                    continue
                
                # Check liquidity/volume when fields are available.
                liquidity_raw = market.get('liquidity')
                volume_raw = market.get('volume')

                liquidity = float(liquidity_raw or 0)
                volume = float(volume_raw or 0)

                if liquidity_raw not in (None, '') and liquidity < self.min_liquidity:
                    continue

                if volume_raw not in (None, '') and volume < self.min_volume:
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
                'primary_token_id': tokens[0].get('token_id') if tokens else None,
                'yes_token_id': next(
                    (t.get('token_id') for t in tokens if str(t.get('outcome', '')).lower() == 'yes'),
                    None,
                ),
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
    
    def _get_history_cache_path(self, market_id: str, token_id: str, days: int) -> str:
        cache_key = hashlib.sha256(
            f"{market_id}:{token_id}:{days}:{self.history_interval}".encode('utf-8')
        ).hexdigest()
        return os.path.join(self.cache_dir, f"history_{cache_key}.json")

    def _normalize_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize CLOB price history payload into backtest points."""
        normalized: List[Dict[str, Any]] = []
        for point in history:
            ts = point.get('t') or point.get('timestamp') or point.get('time')
            price = point.get('p') or point.get('price') or point.get('close')
            volume = point.get('v') or point.get('volume') or 0

            if ts is None or price is None:
                continue

            ts_value = float(ts)
            if ts_value > 1e12:  # milliseconds
                ts_value /= 1000

            normalized.append(
                {
                    'timestamp': datetime.utcfromtimestamp(ts_value).isoformat(),
                    'price': float(price),
                    'volume': float(volume),
                }
            )

        normalized.sort(key=lambda x: x['timestamp'])
        return normalized

    async def fetch_historical_prices(
        self,
        market: Dict[str, Any],
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """Fetch and cache real historical price data for a market token."""
        try:
            market_id = market['id']
            token_id = market.get('yes_token_id') or market.get('primary_token_id')
            if not token_id:
                logger.warning("No token_id found for market %s", market_id)
                if str(market_id).startswith('offline_market_'):
                    self.run_summary['history']['simulated_used'] += 1
                    return self._generate_simulated_history(market_id, market.get('current_price', 0.5), days)
                return []

            cache_path = self._get_history_cache_path(market_id, token_id, days)
            if os.path.exists(cache_path):
                self.run_summary['history']['cache_hits'] += 1
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

            url = f"{self.api_endpoint}/prices-history"
            now = datetime.utcnow()
            market_end = self._parse_iso_datetime(market.get('end_date'))
            anchor_end = market_end if market_end and market_end < now else now
            start_ts = int((anchor_end - timedelta(days=days)).timestamp())
            end_ts = int(anchor_end.timestamp())

            history_points: List[Dict[str, Any]] = []
            chunk_seconds = max(self.history_chunk_days, 1) * 24 * 3600

            # CLOB prices-history enforces max time span per request.
            for chunk_start in range(start_ts, end_ts, chunk_seconds):
                chunk_end = min(chunk_start + chunk_seconds, end_ts)
                params = {
                    'market': token_id,
                    'interval': self.history_interval,
                    'startTs': chunk_start,
                    'endTs': chunk_end,
                }
                payload = await self._request_json(url, params=params)
                if payload is None:
                    logger.warning(
                        "Failed to fetch history chunk market=%s startTs=%s endTs=%s",
                        market_id,
                        chunk_start,
                        chunk_end,
                    )
                    continue

                self.run_summary['history']['api_downloads'] += 1
                history_points.extend(payload.get('history', []))

            if not history_points:
                self.run_summary['history']['failed'] += 1
                if self.use_simulated_history:
                    self.run_summary['history']['simulated_used'] += 1
                    return self._generate_simulated_history(market_id, market.get('current_price', 0.5), days)
                return []

            parsed = self._normalize_history(history_points)
            if parsed:
                # de-duplicate timestamps across chunk boundaries
                deduped = {p['timestamp']: p for p in parsed}
                parsed = [deduped[k] for k in sorted(deduped.keys())]
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed, f)
            return parsed

        except Exception as e:
            logger.error(f"Error fetching historical prices: {e}")
            self.run_summary['history']['failed'] += 1
            if self.use_simulated_history:
                self.run_summary['history']['simulated_used'] += 1
                return self._generate_simulated_history(market.get('id', 'unknown'), market.get('current_price', 0.5), days)
            return []

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
    
    def _market_time_window(self, market: Dict[str, Any], default_start: datetime, default_end: datetime) -> tuple[datetime, datetime]:
        """Return per-market effective backtest window, anchored to close time when needed."""
        market_end = self._parse_iso_datetime(market.get('end_date'))

        if market_end and market_end < default_start:
            market_window_end = market_end
            market_window_start = market_end - timedelta(days=self.lookback_days)
            return market_window_start, market_window_end

        if market_end and market_end < default_end:
            return default_start, market_end

        return default_start, default_end

    def _market_overlaps_window(self, market: Dict[str, Any], start_date: datetime) -> bool:
        end_date = self._parse_iso_datetime(market.get('end_date'))
        if end_date is None:
            return True
        return end_date >= start_date

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
        self.run_summary['markets']['requested'] = max_markets
        markets = await self.fetch_markets_for_backtest()

        # Optional network-restricted fallback: synthetic markets.
        if not markets and self.enable_generated_fallback:
            logger.warning("Falling back to synthetic markets for offline backtest")
            markets = self._generate_fallback_markets(max_markets)
            self.run_summary['markets']['fallback_generated'] = len(markets)
        
        if not markets:
            logger.warning("No markets found for backtest")
            return {'markets': [], 'price_data': {}}
        
        # Drop markets that do not overlap requested backtest window.
        window_markets: List[Dict[str, Any]] = []
        for market in markets:
            if self._market_overlaps_window(market, start_date):
                window_markets.append(market)
            else:
                self.run_summary['markets']['out_of_window_excluded'] += 1

        if not window_markets and markets:
            logger.warning(
                "All candidate markets are outside requested window; auto-adapting to market close time windows"
            )
            window_markets = markets

        markets = window_markets

        # Fetch historical prices and keep only markets with usable data.
        selected_markets: List[Dict[str, Any]] = []
        price_data: Dict[str, List[Dict[str, Any]]] = {}

        for market in markets:
            if len(selected_markets) >= max_markets:
                break

            market_id = market['id']
            prices = await self.fetch_historical_prices(market, days=self.lookback_days)

            if not prices:
                self.run_summary['history']['history_empty_count'] += 1
                continue

            # Filter by per-market adaptive date range (uses close time for old/closed markets).
            market_start, market_end = self._market_time_window(market, start_date, end_date)
            filtered_prices = [
                p for p in prices
                if market_start <= datetime.fromisoformat(p['timestamp']) <= market_end
            ]

            if not filtered_prices:
                self.run_summary['history']['date_filtered_out_count'] += 1
                continue

            selected_markets.append(market)
            price_data[market_id] = filtered_prices

        markets = selected_markets

        if not markets and self.enable_generated_fallback:
            logger.warning("No markets with usable real history; falling back to synthetic markets")
            markets = self._generate_fallback_markets(max_markets)
            price_data = {
                m['id']: self._generate_simulated_history(
                    m['id'],
                    m.get('current_price', 0.5),
                    self.lookback_days,
                )
                for m in markets
            }
            self.run_summary['markets']['fallback_generated'] = len(markets)
            self.run_summary['history']['simulated_used'] += len(markets)

        self.run_summary['markets']['selected'] = len(markets)
            
        
        self.run_summary['history']['markets_with_prices'] = len(price_data)
        logger.info(f"Loaded price data for {len(price_data)} markets")
        logger.info(
            "Run summary: markets=%s history=%s network=%s",
            self.run_summary['markets'],
            self.run_summary['history'],
            self.run_summary['network'],
        )
        
        return {
            'markets': markets,
            'price_data': price_data,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'run_summary': self.run_summary
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
    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            normalized = value.replace('Z', '+00:00')
            dt = datetime.fromisoformat(normalized)
            # Convert aware datetime to naive UTC for internal comparisons.
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None
