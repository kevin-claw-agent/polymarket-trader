# Polymarket 事件交易系统 - 项目大纲

## 1. 项目概述

### 1.1 目标
- 检测 Polymarket 预测市场的价格异常波动
- 通过新闻情感分析识别市场过度反应
- 生成反向交易信号（超卖买入/超买卖出）

### 1.2 核心假设
- 市场会对新闻事件产生过度反应
- 价格与新闻情感出现背离时存在交易机会
- 历史模式可以帮助预测价格回归

---

## 2. 系统架构

### 2.1 数据层
- **Polymarket CLOB API**: 实时价格、订单簿、成交量
- **NewsAPI**: 主流新闻源
- **RSS Feeds**: Reuters, Bloomberg, CoinTelegraph
- **GDELT**: 全球事件数据库

### 2.2 处理层
- **市场监控器**: 价格/成交量异常检测
- **新闻引擎**: 抓取 + NLP情感分析
- **过度反应检测器**: 背离识别算法
- **信号生成器**: 交易信号 + 仓位管理
- **风险管理器**: 熔断 + 止损 + 仓位限制

### 2.3 存储层
- **PostgreSQL**: 市场数据、信号、交易记录
- **Redis**: 缓存、实时状态

### 2.4 输出层
- **Telegram Bot**: 实时交易信号推送
- **Web Dashboard**: 监控面板 + 手动审批
- **Discord**: 辅助通知渠道

---

## 3. 核心算法

### 3.1 异常检测
```
价格异动: |ΔPrice_5m| > 5%  OR  |ΔPrice_1h| > 10%
成交量激增: Volume > 3 × MA20_Volume
流动性预警: Spread > 2% OR Liquidity < $50k
```

### 3.2 过度反应检测算法
```
输入: 价格变动 P, 新闻情感 S

1. 计算预期价格方向:
   if S > 0.3: expected = "up"
   if S < -0.3: expected = "down"
   else: expected = "neutral"

2. 检测背离:
   if expected == "up" AND P.direction == "down":
      divergence = "oversold" (买入机会)
   if expected == "down" AND P.direction == "up":
      divergence = "overbought" (卖出机会)

3. 计算置信度:
   confidence = 0.4 × divergence_strength +
                0.35 × emotion_score +
                0.25 × historical_similarity
```

### 3.3 仓位计算
```
position_size = base_size × (1 + (confidence/100) × (multiplier-1))
约束: position_size ≤ max_position_size
```

---

## 4. 风险管理

### 4.1 仓位限制
- 单市场最大: 5%
- 总敞口最大: 50%
- 相关市场组最大: 15%

### 4.2 损失限制
- 单日最大亏损: 2%
- 单周最大亏损: 5%
- 单个仓位止损: 5-10%

### 4.3 熔断机制
- 触发条件: 市场波动 > 30%
- 冷却时间: 60分钟
- 全局暂停新信号

---

## 5. 信号生命周期

```
Anomaly Detected
       ↓
News Fetched & Analyzed
       ↓
Overreaction Detected?
   Yes → Calculate Confidence
         ↓
    Confidence ≥ 60%?
       Yes → Risk Check
             ↓
        Risk Check Pass?
           Yes → Generate Signal
                 ↓
            Send Alert
                 ↓
            Manual Review
                 ↓
            Execute Trade
                 ↓
            Monitor Position
                 ↓
            Close (TP/SL/Timeout)
```

---

## 6. 部署架构

```
┌─────────────────────────────────────────┐
│  Docker Compose Stack                   │
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Trader  │ │Dashboard│ │ Postgres│   │
│  │ (Core)  │ │ (Flask) │ │  (DB)   │   │
│  └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┘         │
│                   │                     │
│              ┌────┴────┐                │
│              │  Redis  │                │
│              └─────────┘                │
└─────────────────────────────────────────┘
```

---

## 7. 配置文件

### 7.1 监控参数
- 价格阈值: 5分钟5%, 1小时10%, 24小时20%
- 成交量阈值: 3倍平均, 最小$10k
- 检查频率: 30秒

### 7.2 策略参数
- 最低置信度: 60%
- 每日最大信号: 10个
- 冷却时间: 30分钟

### 7.3 API Keys
- NewsAPI
- Telegram Bot
- (可选) Discord Webhook

---

## 8. 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11, AsyncIO |
| 数据 | asyncpg, redis-py |
| HTTP | aiohttp, Flask |
| NLP | transformers (BERT) |
| 部署 | Docker, Docker Compose |
| 监控 | Grafana (可选) |

---

## 9. 项目文件结构

```
polymarket-trader/
├── src/
│   ├── main.py                 # 主入口
│   ├── core/
│   │   ├── data_ingestion.py   # Polymarket数据
│   │   ├── market_monitor.py   # 异常监控
│   │   └── database.py         # 数据库操作
│   ├── news/
│   │   ├── news_fetcher.py     # 新闻抓取
│   │   └── sentiment.py        # 情感分析
│   ├── signals/
│   │   ├── detector.py         # 过度反应检测
│   │   ├── generator.py        # 信号生成
│   │   └── risk_manager.py     # 风险管理
│   ├── alerts/
│   │   └── telegram_bot.py     # 通知机器人
│   └── dashboard/
│       └── app.py              # Web面板
├── config/
│   ├── config.yaml             # 主配置
│   └── strategies.yaml         # 策略配置
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── init.sql
├── docs/
│   ├── ARCHITECTURE.md
│   └── DEPLOYMENT.md
└── requirements.txt
```

---

## 10. 后续优化方向

1. **机器学习模型**: 训练价格预测模型
2. **社交情绪**: 接入 Twitter/Reddit 情绪数据
3. **链上分析**: 监控大额交易/聪明钱动向
4. **回测系统**: 历史数据回测策略表现
5. **自动执行**: 集成 Polymarket 合约自动交易
