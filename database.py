"""Database management for arbitrage bot"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class ArbitrageDatabase:
    """SQLite database manager for arbitrage bot"""
    
    def __init__(self, db_path: str = 'arbitrage_bot.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.init_tables()
    
    def init_tables(self):
        """Create necessary tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Opportunities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                buy_exchange TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_exchange TEXT NOT NULL,
                sell_price REAL NOT NULL,
                profit_percentage REAL NOT NULL,
                detected_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Executed trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id TEXT NOT NULL,
                buy_order_id TEXT NOT NULL,
                sell_order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                buy_exchange TEXT NOT NULL,
                sell_exchange TEXT NOT NULL,
                amount REAL NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                fees_paid REAL NOT NULL,
                final_profit REAL NOT NULL,
                status TEXT NOT NULL,
                executed_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Daily summary table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                total_trades INTEGER,
                total_profit REAL,
                total_loss REAL,
                win_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Error log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database tables initialized")
    
    def log_opportunity(self, opportunity_data: Dict) -> int:
        """Log detected opportunity to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO opportunities 
                (symbol, buy_exchange, buy_price, sell_exchange, sell_price, profit_percentage, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                opportunity_data['symbol'],
                opportunity_data['buy_exchange'],
                opportunity_data['buy_price'],
                opportunity_data['sell_exchange'],
                opportunity_data['sell_price'],
                opportunity_data['profit_percentage'],
                opportunity_data['detected_at']
            ))
            
            conn.commit()
            opp_id = cursor.lastrowid
            conn.close()
            
            return opp_id
        except Exception as e:
            logger.error(f"Error logging opportunity: {e}")
            return None
    
    def log_trade(self, trade_data: Dict) -> int:
        """Log executed trade to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades 
                (opportunity_id, buy_order_id, sell_order_id, symbol, buy_exchange, sell_exchange, 
                 amount, buy_price, sell_price, fees_paid, final_profit, status, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data['opportunity_id'],
                trade_data['buy_order_id'],
                trade_data['sell_order_id'],
                trade_data['symbol'],
                trade_data['buy_exchange'],
                trade_data['sell_exchange'],
                trade_data['amount'],
                trade_data['buy_price'],
                trade_data['sell_price'],
                trade_data['fees_paid'],
                trade_data['final_profit'],
                trade_data['status'],
                trade_data['executed_at']
            ))
            
            conn.commit()
            trade_id = cursor.lastrowid
            conn.close()
            
            return trade_id
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            return None
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Get recent trade history"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trades ORDER BY executed_at DESC LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            trades = [dict(row) for row in rows]
            conn.close()
            
            return trades
        except Exception as e:
            logger.error(f"Error fetching trade history: {e}")
            return []
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Get daily trading statistics"""
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_time = f"{date} 00:00:00"
            end_time = f"{date} 23:59:59"
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN final_profit > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(final_profit) as total_profit,
                    AVG(final_profit) as avg_profit,
                    MIN(final_profit) as worst_trade,
                    MAX(final_profit) as best_trade
                FROM trades
                WHERE executed_at BETWEEN ? AND ? AND status = 'completed'
            ''', (start_time, end_time))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                total_trades = result[0] or 0
                winning_trades = result[1] or 0
                
                return {
                    'date': date,
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
                    'total_profit': result[2] or 0,
                    'average_profit': result[3] or 0,
                    'worst_trade': result[4] or 0,
                    'best_trade': result[5] or 0,
                }
            
            return {
                'date': date,
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'average_profit': 0,
                'worst_trade': 0,
                'best_trade': 0,
            }
        except Exception as e:
            logger.error(f"Error fetching daily stats: {e}")
            return {}
    
    def log_error(self, error_type: str, message: str):
        """Log error to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO error_log (error_type, message, timestamp)
                VALUES (?, ?, ?)
            ''', (error_type, message, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging error: {e}")
    
    def update_trade_status(self, trade_id: int, status: str):
        """Update trade status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE trades SET status = ? WHERE id = ?
            ''', (status, trade_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating trade status: {e}")
