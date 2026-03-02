# Polymarket Backtest System 使用说明

## 快速开始

### 1. 安装依赖

```bash
cd /home/node/.openclaw/workspace/projects/polymarket-trader
pip install -r requirements.txt
```

### 2. 运行回测

```bash
# 默认运行 (价格均值回归策略)
python run_backtest.py

# 使用动量策略
python run_backtest.py --strategy momentum

# 限制测试市场数量
python run_backtest.py --markets 20

# 调整历史数据天数
python run_backtest.py --days 60
```

### 3. 查看结果

回测结果保存在 `backtest_results/` 目录：
- `report_*.html` - 交互式图表报告
- `report_*.json` - 详细数据 JSON

## 配置说明

编辑 `config/backtest.yaml`:

```yaml
# 回测参数
backtest:
  initial_capital: 10000      # 初始资金
  position_size: 0.02         # 每笔交易仓位 (2%)
  fee_rate: 0.002             # 手续费率 (0.2%)

# 市场筛选 (Politics/Finance 高确定性市场)
data:
  min_liquidity: 50000        # 最低流动性 $50k
  min_volume: 100000          # 最低成交量 $100k
  min_traders: 50             # 最低交易者数量

# 策略参数
strategy:
  price_spike_threshold: 0.05 # 价格异动阈值 5%
  volume_surge_threshold: 3.0 # 成交量激增倍数
  min_confidence: 60          # 最低信号置信度
```

## 策略说明

### 价格均值回归策略 (默认)

仅使用价格和成交量数据检测过度反应：

1. **检测逻辑**
   - Z-score ≥ 2 (价格偏离均值2个标准差)
   - 成交量 ≥ 3倍平均
   - 生成反向交易信号

2. **信号类型**
   - `MEAN_REVERSION_LONG` - 超跌买入
   - `MEAN_REVERSION_SHORT` - 超涨卖出
   - `SPIKE_LONG/SHORT` - 价格异动信号

### 动量策略

```bash
python run_backtest.py --strategy momentum
```

跟随价格趋势，5周期动量检测。

## 回测指标

### 收益指标
- **Total Return** - 总收益率
- **Win Rate** - 胜率
- **Profit Factor** - 盈亏比

### 风险指标
- **Max Drawdown** - 最大回撤
- **Sharpe Ratio** - 夏普比率
- **Volatility** - 波动率

### 交易统计
- 平均持仓时间
- 连续盈亏次数
- 按信号类型分析

## 项目结构

```
polymarket-trader/
├── src/backtest/
│   ├── data_loader.py      # 数据加载
│   ├── strategy.py         # 简化策略
│   ├── engine.py           # 回测引擎
│   ├── reporter.py         # 报告生成
│   └── visualizer.py       # 可视化
├── config/backtest.yaml    # 回测配置
├── run_backtest.py         # 入口脚本
└── BACKTEST.md             # 详细文档
```

## 注意事项

1. **数据来源**: 当前使用模拟历史数据，生产环境需连接真实数据源
2. **市场筛选**: 仅包含 Politics/Finance 高流动性市场
3. **简化策略**: 移除了新闻情感分析，仅用价格数据
4. **费用**: 已包含 0.2% 双边手续费

## GitHub 提交

代码已推送至: https://github.com/kevin-claw-agent/polymarket-trader

提交记录:
```
db881d4 Add backtest system for Politics/Finance markets
```
