# System Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POLYMARKET TRADER SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         DATA LAYER                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Polymarket  │  │   NewsAPI   │  │ RSS Feeds   │  │   GDELT     │ │   │
│  │  │   CLOB API  │  │             │  │             │  │             │ │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │   │
│  │         │                │                │                │        │   │
│  │         └────────────────┴────────────────┴────────────────┘        │   │
│  │                                    │                                │   │
│  │                         ┌──────────▼──────────┐                     │   │
│  │                         │  Data Ingestion     │                     │   │
│  │                         │  ├─ WebSocket       │                     │   │
│  │                         │  ├─ REST Polling    │                     │   │
│  │                         │  └─ RSS Parsing     │                     │   │
│  │                         └──────────┬──────────┘                     │   │
│  └────────────────────────────────────┼────────────────────────────────┘   │
│                                       │                                     │
│  ┌────────────────────────────────────┼────────────────────────────────┐   │
│  │                    PROCESSING LAYER │                                │   │
│  │                                     ▼                                │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    Market Monitor                               │ │   │
│  │  │  ├─ Price Volatility Detection  (>5% in 5min, >10% in 1h)      │ │   │
│  │  │  ├─ Volume Surge Detection      (>3x average)                  │ │   │
│  │  │  └─ Liquidity Monitoring        (spread, depth)                │ │   │
│  │  └────────────────────────┬────────────────────────────────────────┘ │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    News Matching Engine                         │ │   │
│  │  │  ├─ NLP Sentiment Analysis                                      │ │   │
│  │  │  ├─ Event Correlation Scoring                                   │ │   │
│  │  │  └─ Relevance Ranking                                           │ │   │
│  │  └────────────────────────┬────────────────────────────────────────┘ │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                 Overreaction Detector                           │ │   │
│  │  │  ├─ Sentiment-Price Divergence Detection                        │ │   │
│  │  │  ├─ Panic/Greed Scoring                                         │ │   │
│  │  │  ├─ Historical Pattern Matching                                 │ │   │
│  │  │  └─ Confidence Scoring Algorithm                                │ │   │
│  │  └────────────────────────┬────────────────────────────────────────┘ │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                  Signal Generator                               │ │   │
│  │  │  ├─ BUY/SELL Signal Generation                                  │ │   │
│  │  │  ├─ Position Size Calculation                                   │ │   │
│  │  │  ├─ Stop-Loss / Take-Profit Calculation                         │ │   │
│  │  │  └─ Risk-Reward Analysis                                        │ │   │
│  │  └────────────────────────┬────────────────────────────────────────┘ │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                   Risk Manager                                  │ │   │
│  │  │  ├─ Exposure Limits (per market: 5%, total: 50%)                │ │   │
│  │  │  ├─ Daily Loss Limits (max 2%)                                  │ │   │
│  │  │  ├─ Correlation Checks                                          │ │   │
│  │  │  └─ Circuit Breakers                                            │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    STORAGE LAYER                                     │   │
│  │  ┌─────────────────┐              ┌─────────────────┐              │   │
│  │  │   PostgreSQL    │              │     Redis       │              │   │
│  │  │  ├─ markets     │              │  ├─ cache       │              │   │
│  │  │  ├─ price_hist  │              │  ├─ sessions    │              │   │
│  │  │  ├─ anomalies   │              │  └─ real-time   │              │   │
│  │  │  ├─ news        │              │                 │              │   │
│  │  │  ├─ signals     │              │                 │              │   │
│  │  │  └─ trades      │              │                 │              │   │
│  │  └─────────────────┘              └─────────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OUTPUT LAYER                                      │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │  Alert Systems  │  │   Dashboard     │  │  Trade Executor │     │   │
│  │  │                 │  │                 │  │                 │     │   │
│  │  │ ├─ Telegram     │  │ ├─ Real-time UI │  │ ├─ Paper Trade  │     │   │
│  │  │ ├─ Discord      │  │ ├─ Signal Queue │  │ └─ Live Trade   │     │   │
│  │  │ └─ Email        │  │ ├─ Analytics    │  │    (Manual)     │     │   │
│  │  │                 │  │ └─ Performance  │  │                 │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Polymarket  │────▶│   Monitor   │────▶│  Anomaly    │
│   Data      │     │             │     │  Detection  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐     ┌─────────────┐           │
│   News      │────▶│  Sentiment  │───────────┤
│   Data      │     │  Analysis   │           │
└─────────────┘     └─────────────┘           ▼
                                       ┌─────────────┐
                                       │ Overreaction│
                                       │  Detection  │
                                       └──────┬──────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   Signal    │
                                       │  Generation │
                                       └──────┬──────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │    Risk     │
                                       │   Check     │
                                       └──────┬──────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         │                    │                    │
                         ▼                    ▼                    ▼
                  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                  │   Alerts    │     │  Dashboard  │     │   Trade     │
                  │             │     │             │     │  Execution  │
                  └─────────────┘     └─────────────┘     └─────────────┘
```

## Signal Generation Logic

```
                    ┌─────────────────┐
                    │  Price Anomaly  │
                    │   Detected      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Fetch Related  │
                    │     News        │
                    └────────┬────────┘
                             │
                             ▼
         ┌───────────────────┴───────────────────┐
         │                                       │
         ▼                                       ▼
┌─────────────────┐                     ┌─────────────────┐
│ Sentiment       │                     │ Price Movement  │
│ Analysis        │                     │ Analysis        │
└────────┬────────┘                     └────────┬────────┘
         │                                       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Check for     │
                    │  Divergence?    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              Yes                           No
              │                             │
              ▼                             ▼
     ┌─────────────────┐          ┌─────────────────┐
     │ Calculate       │          │  Skip Signal    │
     │ Confidence      │          │  (No Trade)     │
     │ Score           │          └─────────────────┘
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐
     │ Confidence >=   │
     │ Threshold?      │
     └────────┬────────┘
              │
    ┌─────────┴──────────┐
    │                    │
   Yes                   No
    │                    │
    ▼                    ▼
┌──────────┐    ┌─────────────────┐
│ Generate │    │  Monitor Only   │
│ Signal   │    │  (Alert Only)   │
└────┬─────┘    └─────────────────┘
     │
     ▼
┌─────────────────┐
│ Risk Manager    │
│ Validation      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
  Pass      Fail
    │         │
    ▼         ▼
┌──────┐  ┌──────────┐
│Emit  │  │ Reject   │
│Alert │  │ Signal   │
└──────┘  └──────────┘
```

## Database Schema

```
┌─────────────────────────────────────────────────────────────────┐
│                          MARKETS                                 │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)        │ TEXT    │ Market identifier                    │
│ slug           │ TEXT    │ URL-friendly name                    │
│ question       │ TEXT    │ Market question                      │
│ description    │ TEXT    │ Detailed description                 │
│ category       │ TEXT    │ Market category                      │
│ price          │ REAL    │ Current price (0-1)                  │
│ volume         │ REAL    │ Trading volume                       │
│ liquidity      │ REAL    │ Market liquidity                     │
│ updated_at     │ TIMESTAMP │ Last update                        │
│ raw_data       │ JSONB   │ Raw API response                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       PRICE_HISTORY                            │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)        │ SERIAL  │ Unique identifier                    │
│ market_id (FK) │ TEXT    │ Reference to markets                 │
│ price          │ REAL    │ Price at timestamp                   │
│ volume         │ REAL    │ Volume at timestamp                  │
│ timestamp      │ TIMESTAMP │ When recorded                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         ANOMALIES                               │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)        │ TEXT    │ Unique anomaly ID                    │
│ market_id (FK) │ TEXT    │ Affected market                      │
│ trigger_type   │ TEXT    │ Type of anomaly                      │
│ severity       │ TEXT    │ low/medium/high/critical             │
│ price_data     │ JSONB   │ Price movement details               │
│ volume_data    │ JSONB   │ Volume surge details                 │
│ processed      │ BOOLEAN │ Whether processed into signal        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                           NEWS                                  │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)        │ TEXT    │ Unique article ID                    │
│ source         │ TEXT    │ News source name                     │
│ title          │ TEXT    │ Article title                        │
│ content        │ TEXT    │ Article content                      │
│ published      │ TIMESTAMP │ Publication time                   │
│ sentiment_score│ REAL    │ -1 to 1 sentiment                    │
│ sentiment_label│ TEXT    │ positive/negative/neutral            │
│ relevance_score│ REAL    │ Relevance to markets (0-1)           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         SIGNALS                                 │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)        │ TEXT    │ Unique signal ID                     │
│ market_id (FK) │ TEXT    │ Target market                        │
│ action         │ TEXT    │ BUY/SELL/HOLD                        │
│ confidence     │ REAL    │ Confidence score (0-100)             │
│ position_size  │ REAL    │ Recommended position size            │
│ entry_price    │ REAL    │ Entry price level                    │
│ stop_loss      │ REAL    │ Stop loss price                      │
│ take_profit    │ REAL    │ Take profit price                    │
│ status         │ TEXT    │ pending/approved/active/closed       │
│ actual_return  │ REAL    │ Actual return when closed            │
│ signal_data    │ JSONB   │ Full signal details                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Interactions

```
┌──────────────┐     WebSocket/REST      ┌──────────────┐
│  Polymarket  │◄───────────────────────►│   Data       │
│    API       │                         │  Ingestion   │
└──────────────┘                         └──────┬───────┘
                                                │
                                                │ Store
                                                ▼
                                         ┌──────────────┐
                                         │  PostgreSQL  │
                                         │    + Redis   │
                                         └──────┬───────┘
                                                │
                                                │ Fetch
                                                ▼
┌──────────────┐     HTTP/JSON         ┌──────────────┐
│   Telegram   │◄─────────────────────►│    Main      │
│     Bot      │                       │    Engine    │
└──────────────┘                       └──────┬───────┘
                                              │
┌──────────────┐     HTTP/WebSocket    ┌─────┴───────┐
│  Dashboard   │◄─────────────────────►│   Signal    │
│   (Flask)    │                       │  Generator  │
└──────────────┘                       └─────────────┘
```
