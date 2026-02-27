-- Initialize database schema
-- This file is automatically executed when the PostgreSQL container starts

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_markets_category ON markets(category);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity);

-- Create view for active signals
CREATE OR REPLACE VIEW active_signals AS
SELECT 
    s.*,
    m.question as market_question_full,
    m.category as market_category
FROM signals s
JOIN markets m ON s.market_id = m.id
WHERE s.status IN ('pending', 'approved', 'active')
ORDER BY s.timestamp DESC;

-- Create view for performance metrics
CREATE OR REPLACE VIEW daily_performance AS
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_signals,
    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_signals,
    COUNT(CASE WHEN actual_return > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN actual_return <= 0 THEN 1 END) as losing_trades,
    AVG(CASE WHEN actual_return IS NOT NULL THEN actual_return END) as avg_return,
    SUM(CASE WHEN actual_return IS NOT NULL THEN actual_return * position_size END) as total_pnl
FROM signals
GROUP BY DATE(timestamp)
ORDER BY date DESC;
