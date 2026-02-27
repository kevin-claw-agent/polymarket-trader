"""
Polymarket Event Trading System - Core Module
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

import yaml
from typing import Dict, Any, Optional

# Configure logging
def setup_logging(config: Dict[str, Any]):
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'))
    
    # Create logs directory
    log_file = log_config.get('file', 'logs/polymarket_trader.log')
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=level,
        format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


class PolymarketTrader:
    """Main trading system orchestrator"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = setup_logging(self.config)
        self.running = False
        
        # Components (initialized later)
        self.data_ingestion = None
        self.market_monitor = None
        self.news_fetcher = None
        self.signal_generator = None
        self.risk_manager = None
        self.alert_system = None
        
        self.logger.info("PolymarketTrader initialized")
    
    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Expand environment variables
        config = self._expand_env_vars(config)
        return config
    
    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand environment variables in config"""
        if isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            import os
            # Expand ${VAR} syntax
            result = obj
            for key, value in os.environ.items():
                result = result.replace(f"${{{key}}}", value)
            return result
        return obj
    
    async def initialize(self):
        """Initialize all system components"""
        self.logger.info("Initializing system components...")
        
        # Import and initialize components
        from src.core.database import Database
        from src.core.data_ingestion import PolymarketDataIngestion
        from src.core.market_monitor import MarketMonitor
        from src.news.news_fetcher import NewsFetcher
        from src.news.sentiment import SentimentAnalyzer
        from src.signals.detector import OverreactionDetector
        from src.signals.generator import SignalGenerator
        from src.signals.risk_manager import RiskManager
        from src.alerts.telegram_bot import TelegramAlert
        
        # Initialize database
        self.db = Database(self.config['database'])
        await self.db.connect()
        
        # Initialize data ingestion
        self.data_ingestion = PolymarketDataIngestion(
            self.config['polymarket'],
            self.db
        )
        
        # Initialize market monitor
        self.market_monitor = MarketMonitor(
            self.config['monitoring'],
            self.db
        )
        
        # Initialize news components
        self.news_fetcher = NewsFetcher(self.config['news'])
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Initialize signal components
        self.overreaction_detector = OverreactionDetector(
            self.config['signals'],
            self.db
        )
        self.signal_generator = SignalGenerator(
            self.config['signals'],
            self.db
        )
        
        # Initialize risk manager
        self.risk_manager = RiskManager(
            self.config['risk'],
            self.db
        )
        
        # Initialize alert system
        if self.config['alerts']['enabled']:
            self.alert_system = TelegramAlert(self.config.get('telegram'))
        
        self.logger.info("All components initialized successfully")
    
    async def run(self):
        """Main system loop"""
        await self.initialize()
        self.running = True
        
        self.logger.info("🚀 Polymarket Trader System started")
        
        # Setup signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: asyncio.create_task(self.shutdown())
            )
        
        try:
            # Start all background tasks
            tasks = [
                asyncio.create_task(self._market_data_loop()),
                asyncio.create_task(self._market_monitor_loop()),
                asyncio.create_task(self._news_loop()),
                asyncio.create_task(self._signal_loop()),
            ]
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"System error: {e}", exc_info=True)
            await self.shutdown()
    
    async def _market_data_loop(self):
        """Continuously fetch market data"""
        while self.running:
            try:
                await self.data_ingestion.fetch_market_data()
                await asyncio.sleep(self.config['monitoring']['check_interval'])
            except Exception as e:
                self.logger.error(f"Market data error: {e}")
                await asyncio.sleep(5)
    
    async def _market_monitor_loop(self):
        """Monitor for price/volume anomalies"""
        while self.running:
            try:
                anomalies = await self.market_monitor.check_anomalies()
                if anomalies:
                    self.logger.info(f"Detected {len(anomalies)} market anomalies")
                    for anomaly in anomalies:
                        await self._handle_anomaly(anomaly)
                await asyncio.sleep(10)
            except Exception as e:
                self.logger.error(f"Market monitor error: {e}")
                await asyncio.sleep(5)
    
    async def _news_loop(self):
        """Fetch and process news"""
        while self.running:
            try:
                news_items = await self.news_fetcher.fetch_latest()
                for item in news_items:
                    sentiment = await self.sentiment_analyzer.analyze(item)
                    await self.db.store_news(item, sentiment)
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                self.logger.error(f"News fetch error: {e}")
                await asyncio.sleep(60)
    
    async def _signal_loop(self):
        """Generate trading signals"""
        while self.running:
            try:
                # Get recent anomalies without signals
                anomalies = await self.db.get_unprocessed_anomalies()
                
                for anomaly in anomalies:
                    # Match with news
                    related_news = await self.db.get_related_news(
                        anomaly['market_id'],
                        hours=1
                    )
                    
                    # Detect overreaction
                    detection = await self.overreaction_detector.detect(
                        anomaly,
                        related_news
                    )
                    
                    if detection['is_overreaction']:
                        # Generate signal
                        signal = await self.signal_generator.generate(
                            anomaly,
                            detection,
                            related_news
                        )
                        
                        # Risk check
                        if await self.risk_manager.approve_signal(signal):
                            await self._emit_signal(signal)
                        else:
                            self.logger.info(f"Signal rejected by risk manager: {signal['id']}")
                
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"Signal generation error: {e}")
                await asyncio.sleep(10)
    
    async def _handle_anomaly(self, anomaly: Dict[str, Any]):
        """Handle detected market anomaly"""
        self.logger.info(f"Anomaly detected: {anomaly}")
        await self.db.store_anomaly(anomaly)
    
    async def _emit_signal(self, signal: Dict[str, Any]):
        """Emit trading signal to alert systems"""
        self.logger.info(f"🎯 SIGNAL GENERATED: {signal['action']} {signal['market']['question']}")
        
        # Store signal
        await self.db.store_signal(signal)
        
        # Send alerts
        if self.alert_system:
            await self.alert_system.send_signal_alert(signal)
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down Polymarket Trader...")
        self.running = False
        
        # Close database connections
        if hasattr(self, 'db'):
            await self.db.close()
        
        self.logger.info("System shutdown complete")


async def main():
    """Entry point"""
    trader = PolymarketTrader()
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())
