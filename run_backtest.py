#!/usr/bin/env python3
"""
Polymarket Backtest Runner

Main script to run backtests on Polymarket data.
Usage:
    python run_backtest.py [--config config/backtest.yaml] [--strategy price_only|momentum]
"""

import asyncio
import argparse
import json
import yaml
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from backtest import (
    BacktestDataLoader,
    PriceOnlyStrategy,
    SimpleMomentumStrategy,
    BacktestEngine,
    BacktestReporter,
    BacktestVisualizer
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)


async def run_backtest(config: dict, strategy_name: str = 'price_only'):
    """Run backtest with given configuration"""

    logger.info("=" * 60)
    logger.info("Starting Polymarket Backtest")
    logger.info("=" * 60)

    # Initialize data loader
    logger.info("Loading market data...")
    data_loader = BacktestDataLoader(config)

    try:
        backtest_data = await data_loader.load_backtest_data(
            max_markets=config['data'].get('max_markets', 50)
        )

        if not backtest_data['markets']:
            logger.error("No markets found for backtest. Check filters.")
            return

        run_summary = backtest_data.get('run_summary', {})
        logger.info(f"Loaded {len(backtest_data['markets'])} markets")
        if run_summary:
            logger.info(f"Data loading summary: {json.dumps(run_summary, ensure_ascii=False)}")
        for m in backtest_data['markets'][:5]:
            logger.info(f"  - {m['question'][:60]}... ({m['category']}, ${m['volume']:,.0f} vol)")

        # Initialize strategy
        if strategy_name == 'price_only':
            strategy = PriceOnlyStrategy(config)
            display_name = "Price-Only Mean Reversion"
        elif strategy_name == 'momentum':
            strategy = SimpleMomentumStrategy(config)
            display_name = "Simple Momentum"
        else:
            logger.error(f"Unknown strategy: {strategy_name}")
            return

        logger.info(f"\nUsing strategy: {display_name}")

        # Generate signals
        logger.info("\nGenerating signals...")
        all_signals = []

        for market in backtest_data['markets']:
            market_id = market['id']
            price_data = backtest_data['price_data'].get(market_id, [])

            if len(price_data) < 25:
                continue

            signals = strategy.detect_signals(market_id, price_data)
            all_signals.extend(signals)

            if signals:
                logger.debug(f"  {market['question'][:40]}...: {len(signals)} signals")

        logger.info(f"Total signals generated: {len(all_signals)}")

        if not all_signals:
            logger.warning("No signals generated. Check strategy parameters.")
            return

        # Run backtest engine
        logger.info("\nRunning backtest simulation...")
        engine = BacktestEngine(config)
        result = engine.run_backtest(all_signals, backtest_data['price_data'])

        # Generate reports
        logger.info("\nGenerating reports...")
        reporter = BacktestReporter(config.get('reporting', {}))
        visualizer = BacktestVisualizer(config.get('reporting', {}))

        # Print summary to console
        reporter.print_summary(result)

        # Generate and save reports
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        # JSON report
        if config.get('reporting', {}).get('save_json', True):
            report = reporter.generate_report(
                result,
                strategy_name=display_name,
                metadata={
                    'config': config,
                    'markets_tested': len(backtest_data['markets']),
                    'date_range': backtest_data.get('date_range'),
                    'run_summary': backtest_data.get('run_summary', {})
                }
            )
            json_path = reporter.save_report(report, f"report_{strategy_name}_{timestamp}.json")
            logger.info(f"JSON report saved: {json_path}")

        # HTML report
        if config.get('reporting', {}).get('save_html', True):
            html_path = visualizer.save_html_report(
                result,
                strategy_name=display_name,
                filename=f"report_{strategy_name}_{timestamp}.html"
            )
            logger.info(f"HTML report saved: {html_path}")

        logger.info("\n" + "=" * 60)
        logger.info("Backtest complete!")
        logger.info("=" * 60)

        return result
    finally:
        await data_loader.close()


def main():
    parser = argparse.ArgumentParser(
        description='Run backtest on Polymarket data'
    )
    parser.add_argument(
        '--config',
        default='config/backtest.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--strategy',
        default='price_only',
        choices=['price_only', 'momentum'],
        help='Strategy to use'
    )
    parser.add_argument(
        '--markets',
        type=int,
        default=None,
        help='Maximum number of markets to test'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Lookback days for historical data'
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    
    # Override with command line args
    if args.markets:
        config['data']['max_markets'] = args.markets
    if args.days:
        config['data']['lookback_days'] = args.days
    
    # Run backtest
    try:
        result = asyncio.run(run_backtest(config, args.strategy))
        sys.exit(0 if result and result.total_trades > 0 else 1)
    except KeyboardInterrupt:
        logger.info("\nBacktest interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
