"""Core arbitrage detection and execution engine"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import json

from exchange_connector import MultiExchangeManager

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents a single arbitrage opportunity"""
    symbol: str
    buy_exchange: str
    buy_price: float
    sell_exchange: str
    sell_price: float
    profit_percentage: float
    detected_at: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        d = asdict(self)
        d['detected_at'] = self.detected_at.isoformat()
        return d


@dataclass
class ExecutedTrade:
    """Represents an executed arbitrage trade"""
    opportunity_id: str
    buy_order_id: str
    sell_order_id: str
    symbol: str
    buy_exchange: str
    sell_exchange: str
    amount: float
    buy_price: float
    sell_price: float
    fees_paid: float
    final_profit: float
    status: str  # 'pending', 'completed', 'failed'
    executed_at: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        d = asdict(self)
        d['executed_at'] = self.executed_at.isoformat()
        return d


class ArbitrageEngine:
    """Main arbitrage detection and execution engine"""
    
    def __init__(self, exchange_manager: MultiExchangeManager, config: Dict):
        """
        Initialize arbitrage engine
        
        Args:
            exchange_manager: MultiExchangeManager instance
            config: Configuration dictionary
        """
        self.exchange_manager = exchange_manager
        self.config = config
        self.active_opportunities = []
        self.completed_trades = []
        self.daily_profit = 0
        self.daily_loss = 0
        
    def scan_for_opportunities(self, trading_pairs: List[str], min_profit: float = None) -> List[ArbitrageOpportunity]:
        """
        Scan all trading pairs for arbitrage opportunities
        
        Args:
            trading_pairs: List of trading pairs to scan
            min_profit: Minimum profit percentage (uses config if None)
            
        Returns:
            List of detected opportunities
        """
        if min_profit is None:
            min_profit = self.config['TRADING_CONFIG']['min_profit_percentage']
        
        opportunities = []
        
        for symbol in trading_pairs:
            try:
                result = self.exchange_manager.find_arbitrage_opportunity(symbol, min_profit)
                
                if result:
                    buy_exchange, buy_price, sell_exchange, sell_price, profit_pct = result
                    
                    opportunity = ArbitrageOpportunity(
                        symbol=symbol,
                        buy_exchange=buy_exchange,
                        buy_price=buy_price,
                        sell_exchange=sell_exchange,
                        sell_price=sell_price,
                        profit_percentage=profit_pct,
                        detected_at=datetime.now()
                    )
                    
                    opportunities.append(opportunity)
                    logger.info(f"Opportunity found: Buy {symbol} on {buy_exchange} at ${buy_price}, "
                               f"Sell on {sell_exchange} at ${sell_price} ({profit_pct:.2f}% profit)")
            
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        self.active_opportunities = opportunities
        return opportunities
    
    def calculate_actual_profit(self, opportunity: ArbitrageOpportunity, amount: float, 
                               executed_amount: float = None) -> float:
        """
        Calculate actual profit after fees
        
        Args:
            opportunity: ArbitrageOpportunity instance
            amount: Amount traded
            executed_amount: Actual executed amount (may differ from requested)
            
        Returns:
            Net profit in USD
        """
        actual_amount = executed_amount or amount
        
        # Get fees
        from config import EXCHANGE_FEES
        buy_fee_pct = EXCHANGE_FEES.get(opportunity.buy_exchange, {}).get('taker', 0.1) / 100
        sell_fee_pct = EXCHANGE_FEES.get(opportunity.sell_exchange, {}).get('taker', 0.1) / 100
        
        # Calculate costs
        buy_cost = actual_amount * opportunity.buy_price * (1 + buy_fee_pct)
        sell_revenue = actual_amount * opportunity.sell_price * (1 - sell_fee_pct)
        
        # Net profit
        net_profit = sell_revenue - buy_cost
        total_fees = (actual_amount * opportunity.buy_price * buy_fee_pct) + \
                     (actual_amount * opportunity.sell_price * sell_fee_pct)
        
        return {
            'net_profit': net_profit,
            'total_fees': total_fees,
            'gross_profit': sell_revenue - (actual_amount * opportunity.buy_price),
            'roi_percentage': (net_profit / buy_cost) * 100 if buy_cost > 0 else 0
        }
    
    def execute_arbitrage(self, opportunity: ArbitrageOpportunity, amount: float = None) -> Optional[ExecutedTrade]:
        """
        Execute an arbitrage trade
        
        Args:
            opportunity: ArbitrageOpportunity to execute
            amount: Amount to trade (uses config if None)
            
        Returns:
            ExecutedTrade or None if execution failed
        """
        try:
            # Determine amount
            if amount is None:
                amount = self.config['TRADING_CONFIG']['max_position_size'] / opportunity.buy_price
            
            # Check daily loss limit
            if self.daily_loss >= self.config['RISK_CONFIG']['max_daily_loss_usd']:
                logger.warning("Daily loss limit reached. Not executing trade.")
                return None
            
            # Check concurrent trades limit
            if len([t for t in self.completed_trades if t.status == 'pending']) >= \
                    self.config['TRADING_CONFIG']['max_concurrent_trades']:
                logger.warning("Max concurrent trades reached.")
                return None
            
            logger.info(f"Executing arbitrage: Buy {opportunity.symbol} on {opportunity.buy_exchange}, "
                       f"Sell on {opportunity.sell_exchange}")
            
            # Execute buy order
            buy_connector = self.exchange_manager.exchanges.get(opportunity.buy_exchange)
            buy_order = buy_connector.execute_buy_order(
                opportunity.symbol,
                amount,
                opportunity.buy_price
            )
            
            if not buy_order:
                logger.error("Buy order failed")
                return None
            
            # Execute sell order
            sell_connector = self.exchange_manager.exchanges.get(opportunity.sell_exchange)
            sell_order = sell_connector.execute_sell_order(
                opportunity.symbol,
                amount,
                opportunity.sell_price
            )
            
            if not sell_order:
                # Cancel buy order if sell fails
                buy_connector.cancel_order(buy_order['id'], opportunity.symbol)
                logger.error("Sell order failed, cancelled buy order")
                return None
            
            # Calculate profit
            profit_info = self.calculate_actual_profit(opportunity, amount, amount)
            
            trade = ExecutedTrade(
                opportunity_id=f"{opportunity.detected_at.timestamp()}",
                buy_order_id=buy_order['id'],
                sell_order_id=sell_order['id'],
                symbol=opportunity.symbol,
                buy_exchange=opportunity.buy_exchange,
                sell_exchange=opportunity.sell_exchange,
                amount=amount,
                buy_price=opportunity.buy_price,
                sell_price=opportunity.sell_price,
                fees_paid=profit_info['total_fees'],
                final_profit=profit_info['net_profit'],
                status='pending',
                executed_at=datetime.now()
            )
            
            self.completed_trades.append(trade)
            
            # Update daily metrics
            if trade.final_profit > 0:
                self.daily_profit += trade.final_profit
            else:
                self.daily_loss += abs(trade.final_profit)
            
            logger.info(f"Trade executed. Net profit: ${trade.final_profit:.2f}, "
                       f"ROI: {profit_info['roi_percentage']:.2f}%")
            
            return trade
        
        except Exception as e:
            logger.error(f"Error executing arbitrage: {e}")
            return None
    
    def get_performance_summary(self) -> Dict:
        """Get summary of trading performance"""
        completed = [t for t in self.completed_trades if t.status == 'completed']
        pending = [t for t in self.completed_trades if t.status == 'pending']
        
        total_profit = sum(t.final_profit for t in completed)
        avg_profit = total_profit / len(completed) if completed else 0
        
        return {
            'total_trades': len(self.completed_trades),
            'completed_trades': len(completed),
            'pending_trades': len(pending),
            'total_profit': total_profit,
            'daily_profit': self.daily_profit,
            'daily_loss': self.daily_loss,
            'average_profit_per_trade': avg_profit,
            'win_rate': (len([t for t in completed if t.final_profit > 0]) / len(completed) * 100) if completed else 0,
        }
