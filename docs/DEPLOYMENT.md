# Deployment Guide

## Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from @BotFather)
- NewsAPI Key (from newsapi.org)
- (Optional) Discord Webhook URL

## Quick Start

### 1. Clone and Configure

```bash
cd polymarket-trader

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 2. Start Services

```bash
cd docker

# Start core services
docker-compose up -d

# Or with monitoring (Grafana)
docker-compose --profile monitoring up -d
```

### 3. Access Dashboard

- **Main Dashboard**: http://localhost:8080
- **Grafana** (if enabled): http://localhost:3000

### 4. Setup Telegram Bot

1. Message @BotFather to create a bot
2. Copy the bot token to `.env`
3. Send `/start` to your bot
4. Get your chat ID:
   ```bash
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
5. Copy chat ID to `.env`
6. Restart: `docker-compose restart trader`

## Configuration

### Trading Parameters

Edit `config/config.yaml`:

```yaml
signals:
  generator:
    min_confidence: 60      # Minimum confidence to generate signal
    max_daily_signals: 10   # Daily signal limit
    
risk:
  exposure:
    max_per_market: 0.05    # Max 5% per market
    max_total: 0.50         # Max 50% total exposure
```

### Strategy Selection

Edit `config/strategies.yaml`:

```yaml
strategies:
  sentiment_divergence:
    enabled: true
    
  panic_buying:
    enabled: true
    
  fomo_shorting:
    enabled: true
```

## Manual Deployment (Without Docker)

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Setup PostgreSQL

```bash
# Install PostgreSQL
# Create database:
createdb polymarket_trader

# Set environment variables
export DB_USER=trader
export DB_PASSWORD=your_password
```

### 3. Setup Redis

```bash
# Install Redis
redis-server
```

### 4. Run the System

```bash
# Start main trading engine
python -m src.main

# In another terminal, start dashboard
python -m src.dashboard.app
```

## Monitoring

### Logs

```bash
# View trader logs
docker-compose logs -f trader

# View all logs
docker-compose logs -f
```

### Database Queries

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U trader -d polymarket_trader

# Useful queries
SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM anomalies WHERE processed = FALSE;
```

## Backup

```bash
# Backup database
docker-compose exec postgres pg_dump -U trader polymarket_trader > backup.sql

# Restore database
docker-compose exec -T postgres psql -U trader polymarket_trader < backup.sql
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

## Troubleshooting

### Circuit Breaker Triggered

Check logs for extreme volatility:
```bash
docker-compose logs trader | grep -i "circuit"
```

### No Signals Generated

1. Check API connectivity:
   ```bash
   curl https://clob.polymarket.com/markets
   ```

2. Verify confidence thresholds in config

3. Check anomaly detection:
   ```sql
   SELECT COUNT(*) FROM anomalies WHERE timestamp > NOW() - INTERVAL '1 hour';
   ```

### Telegram Not Receiving Alerts

1. Verify bot token:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getMe
   ```

2. Check chat ID is correct
3. Ensure bot is not blocked

## Production Considerations

### Security

- Use strong passwords for databases
- Enable dashboard authentication
- Store API keys in environment variables
- Use HTTPS for dashboard (nginx reverse proxy)

### Performance

- Monitor database size and set retention policies
- Adjust Redis memory limits
- Consider read replicas for heavy query loads

### High Availability

- Use managed PostgreSQL (AWS RDS, etc.)
- Deploy multiple trader instances
- Set up monitoring and alerting
