# Polymarket Backtest System

Price-only backtesting system for Polymarket trading strategies on Politics/Finance markets.

## Features

- **Price-Only Strategy**: Detects overreactions using only price and volume data (no news sentiment)
- **Market Filtering**: Focuses on high-liquidity politics and finance markets
- **Performance Metrics**: Sharpe ratio, max drawdown, win rate, profit factor, and more
- **Visual Reports**: Interactive HTML reports with equity curves and trade analysis
- **Multiple Strategies**: Mean reversion and momentum strategies

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Backtest

```bash
# Run with default configuration (price-only strategy)
python run_backtest.py

# Run with momentum strategy
python run_backtest.py --strategy momentum

# Run with custom config
python run_backtest.py --config config/backtest.yaml

# Limit number of markets
python run_backtest.py --markets 20

# Adjust lookback period
python run_backtest.py --days 60
```

### 3. View Results

Results are saved to `backtest_results/`:
- `report_*.json` - Detailed JSON report
- `report_*.html` - Interactive HTML dashboard

## Configuration

Edit `config/backtest.yaml` to customize:

```yaml
backtest:
  initial_capital: 10000      # Starting capital
  position_size: 0.02         # 2% per trade
  max_positions: 10           # Max concurrent trades
  fee_rate: 0.002             # 0.2% trading fees

data:
  min_liquidity: 50000        # $50k minimum liquidity
  min_volume: 100000          # $100k minimum volume
  min_traders: 50             # 50 minimum traders
  max_markets: 50             # Test up to 50 markets

strategy:
  price_spike_threshold: 0.05 # 5% price spike trigger
  volume_surge_threshold: 3.0 # 3x volume surge
  min_confidence: 60          # 60% minimum confidence
```

## Strategies

### 1. Price-Only Mean Reversion (Default)

Detects overreactions when:
- Price moves >2 standard deviations from mean (Z-score ≥ 2)
- Volume surges above 3x average
- Entry on mean reversion expectation

Signals:
- `MEAN_REVERSION_LONG` - Buy after sharp drop
- `MEAN_REVERSION_SHORT` - Sell/short after spike
- `SPIKE_LONG` / `SPIKE_SHORT` - Volume-confirmed spikes

### 2. Simple Momentum

Follows price momentum:
- Enters on confirmed price direction
- Short-term lookback (5 periods)
- 2% momentum threshold

## Output Metrics

### Performance
- **Total Return**: Absolute and percentage returns
- **Win Rate**: Percentage of winning trades
- **Profit Factor**: Gross profit / gross loss

### Risk
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted returns
- **Volatility**: Annualized standard deviation

### Trade Analysis
- Average win/loss
- Consecutive win/loss streaks
- Signal type performance
- Hold time analysis

## Project Structure

```
polymarket-trader/
├── src/backtest/
│   ├── __init__.py
│   ├── data_loader.py      # Historical data loading
│   ├── strategy.py         # Price-only strategies
│   ├── engine.py           # Backtest simulation
│   ├── reporter.py         # Report generation
│   └── visualizer.py       # Charts and HTML reports
├── config/
│   └── backtest.yaml       # Backtest configuration
├── run_backtest.py         # Main entry point
└── backtest_results/       # Output directory
```

## Example Output

```
============================================================
BACKTEST RESULTS SUMMARY
============================================================

Total Trades:        45
Winning Trades:      27 (60.0%)
Losing Trades:       18

Total Return:        $892.45 (8.92%)
Max Drawdown:        -$234.12 (-2.34%)
Sharpe Ratio:        1.45
Profit Factor:       2.1
Avg Hold Time:       18.5 hours
============================================================
```

## Advanced Usage

### Programmatic Usage

```python
from src.backtest import (
    BacktestDataLoader,
    PriceOnlyStrategy,
    BacktestEngine
)

# Load config
with open('config/backtest.yaml') as f:
    config = yaml.safe_load(f)

# Load data
loader = BacktestDataLoader(config)
data = await loader.load_backtest_data()

# Run strategy
strategy = PriceOnlyStrategy(config)
signals = []
for market in data['markets']:
    market_signals = strategy.detect_signals(market['id'], data['price_data'][market['id']])
    signals.extend(market_signals)

# Run backtest
engine = BacktestEngine(config)
result = engine.run_backtest(signals, data['price_data'])

# Access results
print(f"Return: {result.total_return_percent:.2f}%")
print(f"Win Rate: {result.win_rate:.1%}")
```

### Custom Strategy

```python
from src.backtest.strategy import PriceOnlyStrategy

class MyStrategy(PriceOnlyStrategy):
    def detect_signals(self, market_id, price_data):
        # Custom signal detection logic
        signals = []
        # ... your logic here
        return signals
```

## Notes

- **Simulated Data**: The current implementation generates simulated historical data for demonstration. In production, connect to a real historical data source.
- **Politics/Finance Focus**: Markets are filtered for politics and finance categories only.
- **No News Data**: This backtest uses only price/volume data, no sentiment analysis.

## License

MIT License - See main project LICENSE
