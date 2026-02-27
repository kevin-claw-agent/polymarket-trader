"""
Telegram Alert Bot Module
Sends trading alerts via Telegram
"""

import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TelegramAlert:
    """Telegram bot for sending trading alerts"""
    
    def __init__(self, config: Optional[Dict[str, Any]]):
        self.config = config or {}
        self.bot_token = config.get('bot_token')
        self.chat_id = config.get('chat_id')
        
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured - alerts disabled")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def send_signal_alert(self, signal: Dict[str, Any]):
        """Send a trading signal alert"""
        if not self.base_url:
            return
        
        try:
            message = self._format_signal_message(signal)
            await self._send_message(message, parse_mode='Markdown')
            
            # Send follow-up with news details if available
            if signal.get('news'):
                news_message = self._format_news_summary(signal)
                if news_message:
                    await self._send_message(news_message, parse_mode='Markdown')
                    
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
    
    async def send_anomaly_alert(self, anomaly: Dict[str, Any]):
        """Send an anomaly detection alert"""
        if not self.base_url:
            return
        
        try:
            message = self._format_anomaly_message(anomaly)
            await self._send_message(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error sending anomaly alert: {e}")
    
    async def send_risk_alert(self, risk_event: Dict[str, Any]):
        """Send a risk management alert"""
        if not self.base_url:
            return
        
        try:
            message = self._format_risk_message(risk_event)
            await self._send_message(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error sending risk alert: {e}")
    
    async def send_daily_summary(self, summary: Dict[str, Any]):
        """Send daily trading summary"""
        if not self.base_url:
            return
        
        try:
            message = self._format_daily_summary(summary)
            await self._send_message(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
    
    def _format_signal_message(self, signal: Dict[str, Any]) -> str:
        """Format trading signal as Telegram message"""
        action = signal['signal']['action']
        market = signal['market']
        analysis = signal['analysis']
        sig = signal['signal']
        
        # Emoji based on action
        action_emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
        confidence_emoji = "🔥" if analysis['confidence'] > 80 else "✅" if analysis['confidence'] > 60 else "⚠️"
        
        message = f"""
{action_emoji} *TRADING SIGNAL* {confidence_emoji}

*Market:* {market['question'][:200]}{'...' if len(market['question']) > 200 else ''}
*Category:* {market.get('category', 'General').title()}

*Action:* {action}
*Confidence:* {analysis['confidence']:.0f}%
*Position Size:* {sig['position_size_percent']}

*Price Levels:*
• Entry: {sig['entry_price']}
• Stop Loss: {sig['stop_loss']}
• Take Profit: {sig['take_profit']}
• R:R Ratio: {sig['risk_reward_ratio']}:1

*Analysis:*
• Sentiment: {analysis['sentiment_label'].title()} ({analysis['sentiment_score']:+.2f})
• Divergence: {'Yes' if analysis['divergence_detected'] else 'No'}
• Emotion: {analysis['emotion_type'].title()} ({analysis['emotion_score']:.0f}/100)
• Historical Events: {analysis['historical_similar_events']}

*Reasoning:*
{sig['reasoning'][:300]}{'...' if len(sig['reasoning']) > 300 else ''}

*Signal ID:* `{signal['id']}`
⏱ Expected Hold: {sig['expected_hold_time']}
"""
        return message
    
    def _format_news_summary(self, signal: Dict[str, Any]) -> Optional[str]:
        """Format news summary for Telegram"""
        news_items = signal.get('news', [])
        if not news_items:
            return None
        
        message = "📰 *Related News:*\n\n"
        
        for i, news in enumerate(news_items[:3], 1):
            sentiment = "🟢" if news.get('sentiment_label') == 'positive' else "🔴" if news.get('sentiment_label') == 'negative' else "⚪"
            message += f"{i}. {sentiment} *{news['source']}*\n"
            message += f"   {news['title'][:100]}{'...' if len(news['title']) > 100 else ''}\n"
            if news.get('sentiment_score'):
                message += f"   Sentiment: {news['sentiment_score']:+.2f}\n"
            message += "\n"
        
        return message
    
    def _format_anomaly_message(self, anomaly: Dict[str, Any]) -> str:
        """Format anomaly alert"""
        severity_emoji = "🔴" if anomaly.get('severity') == 'critical' else "🟠" if anomaly.get('severity') == 'high' else "🟡"
        
        message = f"""
{severity_emoji} *MARKET ANOMALY DETECTED*

*Market:* {anomaly.get('market_question', 'Unknown')[:200]}
*Trigger:* {anomaly.get('trigger_type', 'Unknown').replace('_', ' ').title()}
*Severity:* {anomaly.get('severity', 'Unknown').upper()}

*Price Data:*
"""
        
        price_data = anomaly.get('price_data', {})
        if 'change_5m' in price_data:
            change = price_data['change_5m']
            emoji = "📈" if change.get('direction') == 'up' else "📉"
            message += f"• 5m: {emoji} {change.get('direction').upper()} {change.get('percent'):.2f}%\n"
        
        if 'change_1h' in price_data:
            change = price_data['change_1h']
            emoji = "📈" if change.get('direction') == 'up' else "📉"
            message += f"• 1h: {emoji} {change.get('direction').upper()} {change.get('percent'):.2f}%\n"
        
        volume_data = anomaly.get('volume_data', {})
        if 'volume_surge' in volume_data:
            vs = volume_data['volume_surge']
            message += f"\n📊 Volume: {vs.get('ratio', 0):.1f}x average\n"
        
        message += f"\n*Anomaly ID:* `{anomaly.get('id', 'N/A')}`"
        
        return message
    
    def _format_risk_message(self, risk_event: Dict[str, Any]) -> str:
        """Format risk alert"""
        event_type = risk_event.get('type', 'unknown')
        
        if event_type == 'circuit_breaker':
            message = f"""
🚨 *CIRCUIT BREAKER TRIGGERED* 🚨

Extreme volatility detected!

*Market:* {risk_event.get('market', 'Unknown')}
*Volatility:* {risk_event.get('volatility', 0):.1f}%
*Cooldown Until:* {risk_event.get('cooldown_until', 'Unknown')}

All trading paused until cooldown expires.
"""
        elif event_type == 'stop_loss':
            message = f"""
⛔ *STOP LOSS TRIGGERED*

*Signal ID:* `{risk_event.get('signal_id', 'N/A')}`
*Exit Price:* {risk_event.get('exit_price', 'N/A')}
*PnL:* {risk_event.get('pnl', 0):+.2%}
*Reason:* {risk_event.get('reason', 'Unknown').replace('_', ' ').title()}
"""
        elif event_type == 'daily_limit':
            message = f"""
⚠️ *DAILY LOSS LIMIT REACHED*

*Daily PnL:* {risk_event.get('daily_pnl', 0):.2%}
*Limit:* {risk_event.get('limit', 0):.2%}

No new positions will be opened today.
"""
        else:
            message = f"""
⚠️ *RISK ALERT*

{str(risk_event)}
"""
        
        return message
    
    def _format_daily_summary(self, summary: Dict[str, Any]) -> str:
        """Format daily summary"""
        pnl = summary.get('total_pnl', 0)
        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        
        message = f"""
📊 *DAILY TRADING SUMMARY*

*Date:* {summary.get('date', datetime.now().strftime('%Y-%m-%d'))}

*Performance:*
{pnl_emoji} Total PnL: {pnl:+.2%}
• Win Rate: {summary.get('win_rate', 0):.1f}%
• Total Trades: {summary.get('total_trades', 0)}
• Winning Trades: {summary.get('winning_trades', 0)}
• Losing Trades: {summary.get('losing_trades', 0)}

*Signals:*
• Generated: {summary.get('signals_generated', 0)}
• Executed: {summary.get('signals_executed', 0)}
• Rejected: {summary.get('signals_rejected', 0)}

*Risk Metrics:*
• Max Drawdown: {summary.get('max_drawdown', 0):.2%}
• Exposure: {summary.get('current_exposure', 0):.1%}

*Active Positions:* {summary.get('open_positions', 0)}
"""
        return message
    
    async def _send_message(self, text: str, parse_mode: str = 'HTML'):
        """Send message to Telegram"""
        if not self.base_url or not self.chat_id:
            return
        
        session = await self._get_session()
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                data = await response.text()
                logger.error(f"Telegram API error: {response.status} - {data}")
            else:
                logger.debug("Telegram message sent successfully")
    
    async def send_approval_request(self, signal: Dict[str, Any]) -> bool:
        """Send signal approval request with buttons"""
        if not self.base_url:
            return False
        
        try:
            message = self._format_signal_message(signal)
            message += "\n\n*ACTION REQUIRED:* Approve this signal?"
            
            # Create inline keyboard
            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '✅ Approve', 'callback_data': f"approve:{signal['id']}"},
                        {'text': '❌ Reject', 'callback_data': f"reject:{signal['id']}"}
                    ],
                    [
                        {'text': '⏭ Skip', 'callback_data': f"skip:{signal['id']}"}
                    ]
                ]
            }
            
            session = await self._get_session()
            url = f"{self.base_url}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'reply_markup': keyboard
            }
            
            async with session.post(url, json=payload) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Error sending approval request: {e}")
            return False
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
