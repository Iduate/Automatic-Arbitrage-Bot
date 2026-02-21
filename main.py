"""Main arbitrage bot runner"""

import logging
import time
from typing import Dict, List
from datetime import datetime, timedelta
import json

from config import EXCHANGES, TRADING_CONFIG, LOG_CONFIG
from exchange_connector import MultiExchangeManager
from arbitrage_engine import ArbitrageEngine
from database import ArbitrageDatabase


# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_CONFIG['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_CONFIG['log_file']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ArbitrageBot:
    """Main arbitrage bot orchestrator"""
    
    def __init__(self, config_exchanges: Dict, config_trading: Dict, config_risk: Dict, config_fees: Dict):
        """
        Initialize arbitrage bot
        
        Args:
            config_exchanges: Exchange configurations
            config_trading: Trading configurations
            config_risk: Risk management configurations
            config_fees: Exchange fee configurations
        """
        logger.info("Initializing Arbitrage Bot...")
        
        # Store configs
        self.config = {
            'EXCHANGES': config_exchanges,
            'TRADING_CONFIG': config_trading,
            'RISK_CONFIG': config_risk,
            'EXCHANGE_FEES': config_fees,
        }
        
        # Initialize components
        self.exchange_manager = MultiExchangeManager(config_exchanges)
        self.engine = ArbitrageEngine(self.exchange_manager, self.config)
        self.database = ArbitrageDatabase()
        
        # Status tracking
        self.is_running = False
        self.last_scan_time = None
        self.scan_count = 0
        self.last_opportunity_time = None
        
        logger.info("Arbitrage Bot initialized successfully")
    
    def run(self, scan_interval: int = 5, max_runtime: int = None):
        """
        Main bot loop
        
        Args:
            scan_interval: Seconds between scans
            max_runtime: Maximum runtime in seconds (None for infinite)
        """
        self.is_running = True
        start_time = datetime.now()
        
        logger.info(f"Starting bot loop (scan interval: {scan_interval}s)")
        
        try:
            while self.is_running:
                try:
                    # Check max runtime
                    if max_runtime and (datetime.now() - start_time).total_seconds() > max_runtime:
                        logger.info("Max runtime reached")
                        break
                    
                    # Scan for opportunities
                    self.scan_for_opportunities()
                    
                    # Wait for next scan
                    time.sleep(scan_interval)
                
                except KeyboardInterrupt:
                    logger.info("Bot interrupted by user")
                    break
                except Exception as e:
                    logger.error(f"Error in bot loop: {e}")
                    self.database.log_error("BotLoopError", str(e))
                    time.sleep(scan_interval)
        
        finally:
            self.stop()
    
    def scan_for_opportunities(self):
        """Scan for arbitrage opportunities"""
        try:
            self.last_scan_time = datetime.now()
            self.scan_count += 1
            
            # Scan for opportunities
            opportunities = self.engine.scan_for_opportunities(
                self.config['TRADING_CONFIG']['trading_pairs'],
                self.config['TRADING_CONFIG']['min_profit_percentage']
            )
            
            logger.info(f"Scan #{self.scan_count}: Found {len(opportunities)} opportunities")
            
            # Log all opportunities
            for opp in opportunities:
                self.database.log_opportunity(opp.to_dict())
                self.last_opportunity_time = datetime.now()
                
                # Auto-execute if configured
                if self.should_execute():
                    self.execute_best_opportunity(opportunities)
                    break
        
        except Exception as e:
            logger.error(f"Error during opportunity scan: {e}")
            self.database.log_error("ScanError", str(e))
    
    def execute_best_opportunity(self, opportunities: List) -> bool:
        """
        Execute the best opportunity
        
        Args:
            opportunities: List of opportunities (should be sorted by profit)
            
        Returns:
            True if execution attempted
        """
        if not opportunities:
            return False
        
        try:
            # Get best opportunity (highest profit)
            best = max(opportunities, key=lambda x: x.profit_percentage)
            
            logger.info(f"Executing best opportunity: {best.symbol} "
                       f"({best.profit_percentage:.2f}% profit)")
            
            # Execute trade
            trade = self.engine.execute_arbitrage(best)
            
            if trade:
                self.database.log_trade(trade.to_dict())
                logger.info(f"Trade executed successfully. Net profit: ${trade.final_profit:.2f}")
                return True
            else:
                logger.warning("Trade execution failed")
                return False
        
        except Exception as e:
            logger.error(f"Error executing opportunity: {e}")
            self.database.log_error("ExecutionError", str(e))
            return False
    
    def should_execute(self) -> bool:
        """Determine if bot should execute trades"""
        # Can add more sophisticated logic here
        return True
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        perf = self.engine.get_performance_summary()
        daily_stats = self.database.get_daily_stats()
        
        return {
            'status': 'running' if self.is_running else 'stopped',
            'scan_count': self.scan_count,
            'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'last_opportunity': self.last_opportunity_time.isoformat() if self.last_opportunity_time else None,
            'active_opportunities': len(self.engine.active_opportunities),
            'performance': perf,
            'daily_stats': daily_stats,
        }
    
    def print_status(self):
        """Print bot status to console"""
        status = self.get_status()
        
        print("\n" + "="*60)
        print("ARBITRAGE BOT STATUS")
        print("="*60)
        print(f"Status: {status['status']}")
        print(f"Scans completed: {status['scan_count']}")
        print(f"Last scan: {status['last_scan']}")
        print(f"Active opportunities: {status['active_opportunities']}")
        print("\nPerformance:")
        for key, value in status['performance'].items():
            print(f"  {key}: {value}")
        print("\nDaily Stats:")
        for key, value in status['daily_stats'].items():
            if key != 'date':
                print(f"  {key}: {value}")
        print("="*60 + "\n")
    
    def stop(self):
        """Stop the bot"""
        logger.info("Stopping bot...")
        self.is_running = False
        self.print_status()
        logger.info("Bot stopped")


def main():
    """Main entry point"""
    try:
        # Import configs
        from config import (
            EXCHANGES, TRADING_CONFIG, RISK_CONFIG, EXCHANGE_FEES
        )
        
        # Initialize bot
        bot = ArbitrageBot(
            EXCHANGES,
            TRADING_CONFIG,
            RISK_CONFIG,
            EXCHANGE_FEES
        )
        
        # Run bot
        # Run for demonstration (comment out for infinite loop)
        # bot.run(scan_interval=5, max_runtime=300)
        
        # For infinite loop:
        bot.run(scan_interval=5)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
