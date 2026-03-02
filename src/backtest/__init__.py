"""
Polymarket Backtest Module

Provides backtesting functionality for trading strategies on Polymarket data.
"""

from .data_loader import BacktestDataLoader
from .strategy import PriceOnlyStrategy, SimpleMomentumStrategy
from .engine import BacktestEngine, BacktestResult
from .reporter import BacktestReporter
from .visualizer import BacktestVisualizer

__all__ = [
    'BacktestDataLoader',
    'PriceOnlyStrategy',
    'SimpleMomentumStrategy',
    'BacktestEngine',
    'BacktestResult',
    'BacktestReporter',
    'BacktestVisualizer'
]

__version__ = '1.0.0'
