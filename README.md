# Polymarket Event Trading System

针对 Polymarket 预测市场事件过度反应的半自动交易系统。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           POLYMARKET TRADER SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Data Ingestion │    │  News Matching  │    │ Signal Generator│         │
│  │     Layer       │───▶│     Engine      │───▶│                 │         │
│  │                 │    │                 │    │                 │         │
│  │ • Polymarket WS │    │ • NewsAPI       │    │ • Overreaction  │         │
│  │ • REST API      │    │ • RSS Feeds     │    │   Detection     │         │
│  │ • Blockchain    │    │ • NLP Sentiment │    │ • Signal Scoring│         │
│  │   Events        │    │ • Event Matching│    │ • Risk Check    │         │
│  └─────────────────┘    └─────────────────┘    └────────┬────────┘         │
│           │                      │                       │                  │
│           ▼                      ▼                       ▼                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      PostgreSQL + Redis                          │       │
│  │         (Market Data, News, Signals, Performance)               │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                │
│           ▼                                                                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Alert System   │    │   Web Dashboard │    │  Trade Executor │         │
│  │                 │    │                 │    │   (Manual Review)│        │
│  │ • Telegram Bot  │    │ • Real-time UI  │    │                 │         │
│  │ • Discord Bot   │    │ • Signal Queue  │    │ • Paper Trading │         │
│  │ • Email Alerts  │    │ • Analytics     │    │ • Live Trading  │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心策略：事件过度反应交易

### 1. 检测信号
- **价格异动**: 5分钟内波动 >5%, 1小时内 >10%
- **成交量激增**: 超过20周期平均成交量的3倍
- **流动性突变**: 订单簿深度异常变化

### 2. 新闻验证
- 实时抓取相关新闻
- NLP情感分析
- 事件相关性匹配

### 3. 过度反应判断
- 新闻情感 vs 价格方向背离
- 历史相似事件对比
- 市场情绪极端值检测

### 4. 交易信号
- **反向交易**: 市场过度乐观→做空, 过度悲观→做多
- 置信度评分: 0-100%
- 建议仓位大小
- 止损/止盈价位

## 项目结构

```
polymarket-trader/
├── config/
│   ├── config.yaml           # 主配置
│   └── strategies.yaml       # 策略参数
├── src/
│   ├── __init__.py
│   ├── main.py               # 入口点
│   ├── core/
│   │   ├── __init__.py
│   │   ├── data_ingestion.py # Polymarket数据获取
│   │   ├── market_monitor.py # 市场监控
│   │   └── database.py       # 数据库操作
│   ├── news/
│   │   ├── __init__.py
│   │   ├── news_fetcher.py   # 新闻抓取
│   │   ├── sentiment.py      # 情感分析
│   │   └── matcher.py        # 事件匹配
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── detector.py       # 过度反应检测
│   │   ├── generator.py      # 信号生成
│   │   └── risk_manager.py   # 风险管理
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── telegram_bot.py   # Telegram通知
│   │   └── discord_bot.py    # Discord通知
│   └── dashboard/
│       ├── __init__.py
│       └── app.py            # Web仪表盘
├── tests/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 填入你的 API keys
```

### 3. 启动系统
```bash
python src/main.py
```

### 4. 启动仪表盘
```bash
python src/dashboard/app.py
```

## 配置文件说明

### config.yaml
- 监控市场列表
- 价格/成交量阈值
- API endpoints
- 数据库连接

### strategies.yaml
- 过度反应检测参数
- 置信度权重
- 风险管理规则

## 信号示例

```json
{
  "id": "sig_001",
  "timestamp": "2024-01-15T14:30:00Z",
  "market": {
    "id": "0x1234...",
    "question": "Will Bitcoin exceed $50k by March?",
    "category": "crypto"
  },
  "trigger": {
    "type": "price_spike",
    "change_5m": -12.5,
    "volume_surge": 4.2
  },
  "news": [
    {
      "source": "Reuters",
      "title": "SEC delays Bitcoin ETF decision",
      "sentiment": -0.3,
      "relevance": 0.85
    }
  ],
  "analysis": {
    "sentiment_price_divergence": true,
    "panic_score": 78,
    "confidence": 72
  },
  "signal": {
    "action": "BUY",
    "reasoning": "Market overreacting to minor SEC news. Sentiment (-0.3) doesn't justify -12.5% price drop.",
    "position_size": "2%",
    "entry": 0.35,
    "stop_loss": 0.28,
    "take_profit": 0.48
  }
}
```

## 风险管理

- 单市场最大敞口: 5%
- 单日最大亏损: 2%
- 同时持仓上限: 10个市场
- 相关性检查: 避免高度相关市场重复持仓

## 免责声明

这是一个研究性质的交易系统。所有信号仅供参考，不构成投资建议。加密货币和预测市场交易风险极高，可能导致全部本金损失。
