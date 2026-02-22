"""Integrated Pool Bot - DeFi pooling system with automated arbitrage"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from config import EXCHANGES, TRADING_CONFIG, RISK_CONFIG, EXCHANGE_FEES
from exchange_connector import MultiExchangeManager
from arbitrage_engine import ArbitrageEngine
from database import ArbitrageDatabase
from pool_contract import PoolSmartContract, PoolMember
from product_registry import ProductRegistry, Product
from insurance_reserve import InsuranceReserve
from validators import ValidatorNetwork, Validator, ValidatorRole


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pool_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PoolBot:
    """
    Integrated Pool Bot combining DeFi pooling with automated trading
    Features: Smart contract pool, multiple products, insurance, validators
    """
    
    def __init__(self, pool_name: str, max_members: int = None, min_contribution: float = 100):
        """
        Initialize Pool Bot
        
        Args:
            pool_name: Name of the pool
            max_members: Maximum pool members
            min_contribution: Minimum capital contribution
        """
        logger.info(f"Initializing Pool Bot: {pool_name}")
        
        # Core components
        self.pool = PoolSmartContract(pool_name, max_members, min_contribution)
        self.registry = ProductRegistry()
        self.insurance = InsuranceReserve(initial_reserve=0, reserve_percentage=5)
        self.validators = ValidatorNetwork(required_approvals=2, require_lead_approval=True)
        
        # Exchange and trading
        self.exchange_manager = MultiExchangeManager(EXCHANGES)
        self.engine = ArbitrageEngine(self.exchange_manager, {
            'TRADING_CONFIG': TRADING_CONFIG,
            'RISK_CONFIG': RISK_CONFIG,
            'EXCHANGE_FEES': EXCHANGE_FEES,
        })
        self.database = ArbitrageDatabase()
        
        # Status tracking
        self.is_running = False
        self.total_profit_generated = 0
        self.total_trades_executed = 0
        
        # Register default product (Arbitrage)
        self._register_default_products()
        
        logger.info("Pool Bot initialized successfully")
    
    def _register_default_products(self):
        """Register default products"""
        try:
            # Arbitrage product
            arbitrage_product = Product(
                product_id='arbitrage_v1',
                name='Arbitrage Trading',
                description='Automatic cryptocurrency arbitrage across exchanges',
                category='arbitrage',
                enabled=True,
                config=TRADING_CONFIG,
                handler_function=self.execute_arbitrage_product
            )
            
            self.registry.register_product(arbitrage_product)
            logger.info("Default products registered")
        
        except Exception as e:
            logger.error(f"Error registering products: {e}")
    
    def add_pool_member(self, member_address: str, capital: float) -> bool:
        """
        Add a member to the pool
        
        Args:
            member_address: Member wallet address
            capital: Capital contribution
            
        Returns:
            True if added successfully
        """
        try:
            success = self.pool.add_member(member_address, capital)
            
            if success:
                # Allocate insurance for new member
                member_insurance = capital * 0.05  # 5% insurance
                logger.info(f"Member {member_address} added with ${capital} capital")
            
            return success
        
        except Exception as e:
            logger.error(f"Error adding member: {e}")
            return False
    
    def remove_pool_member(self, member_address: str) -> bool:
        """Remove a member from the pool"""
        try:
            success = self.pool.remove_member(member_address)
            
            if success:
                logger.info(f"Member {member_address} removed from pool")
            
            return success
        
        except Exception as e:
            logger.error(f"Error removing member: {e}")
            return False
    
    def register_custom_product(self, product_id: str, name: str, category: str, 
                               config: Dict, handler=None) -> bool:
        """
        Register a custom product/service
        
        Args:
            product_id: Unique product ID
            name: Product name
            category: Product category
            config: Product configuration
            handler: Handler function
            
        Returns:
            True if registered successfully
        """
        try:
            product = Product(
                product_id=product_id,
                name=name,
                description=f"{name} trading service",
                category=category,
                enabled=True,
                config=config,
                handler_function=handler
            )
            
            success = self.registry.register_product(product, handler)
            
            if success:
                logger.info(f"Custom product registered: {name}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error registering custom product: {e}")
            return False
    
    def add_validator(self, validator_id: str, role: str = "SENIOR", address: str = None) -> bool:
        """
        Add a validator to approve trades
        
        Args:
            validator_id: Unique validator ID
            role: Validator role (JUNIOR, SENIOR, LEAD, ADMIN)
            address: Wallet address
            
        Returns:
            True if added successfully
        """
        try:
            role_enum = ValidatorRole[role.upper()]
            validator = Validator(validator_id, role_enum, address)
            
            success = self.validators.add_validator(validator)
            
            if success:
                logger.info(f"Validator {validator_id} added with role {role}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error adding validator: {e}")
            return False
    
    def execute_arbitrage_product(self) -> Dict:
        """Execute arbitrage trading product"""
        try:
            opportunities = self.engine.scan_for_opportunities(
                TRADING_CONFIG['trading_pairs'],
                TRADING_CONFIG['min_profit_percentage']
            )
            
            executed = 0
            total_profit = 0
            
            for opportunity in opportunities:
                # Submit for validation
                trade_id = f"trade_{datetime.now().timestamp()}"
                trade_data = opportunity.to_dict()
                
                self.validators.submit_trade_for_validation(trade_id, trade_data)
                
                # For demo: auto-approve if validators exist
                if len(self.validators.validators) == 0:
                    # Auto-execute if no validators
                    trade = self.engine.execute_arbitrage(opportunity)
                else:
                    # Wait for validator approval
                    for validator_id in list(self.validators.validators.keys())[:2]:
                        self.validators.approve_trade(trade_id, validator_id)
                    
                    # Check if approved
                    if trade_id in self.validators.approved_trades:
                        trade = self.engine.execute_arbitrage(opportunity)
                    else:
                        trade = None
                
                if trade:
                    self.database.log_trade(trade.to_dict())
                    executed += 1
                    total_profit += trade.final_profit
                    self.total_trades_executed += 1
            
            # Allocate profit to insurance reserve
            insurance_allocation = self.insurance.allocate_profit_to_reserve(total_profit)
            
            # Distribute remaining profit to members
            remaining_profit = total_profit - insurance_allocation
            if remaining_profit > 0:
                distribution = self.pool.distribute_profit(remaining_profit)
                self.total_profit_generated += remaining_profit
            
            return {
                'executed_trades': executed,
                'total_profit': total_profit,
                'insurance_allocated': insurance_allocation,
                'member_distribution': distribution if remaining_profit > 0 else {},
            }
        
        except Exception as e:
            logger.error(f"Error executing arbitrage product: {e}")
            return {}
    
    def get_pool_overview(self) -> Dict:
        """Get complete pool overview"""
        try:
            pool_stats = self.pool.get_pool_stats()
            insurance_health = self.insurance.get_reserve_health()
            validator_stats = self.validators.get_validator_stats()
            registry_stats = self.registry.get_registry_stats()
            
            return {
                'pool': pool_stats,
                'insurance': insurance_health,
                'validators': validator_stats,
                'products': registry_stats,
                'total_profit_generated': self.total_profit_generated,
                'total_trades_executed': self.total_trades_executed,
                'timestamp': datetime.now().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error getting pool overview: {e}")
            return {}
    
    def get_member_status(self, member_address: str) -> Optional[Dict]:
        """Get member details"""
        try:
            member = self.pool.members.get(member_address)
            
            if not member:
                return None
            
            balance = self.pool.get_member_balance(member_address)
            
            return {
                'address': member_address,
                'capital_contributed': member.capital_contributed,
                'shares_owned': member.shares_owned,
                'current_balance': balance,
                'profit': balance - member.capital_contributed if balance else 0,
                'status': member.status,
                'joined_date': member.joined_date.isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error getting member status: {e}")
            return None
    
    def print_pool_summary(self):
        """Print pool summary to console"""
        overview = self.get_pool_overview()
        
        print("\n" + "="*70)
        print("POOL BOT SUMMARY")
        print("="*70)
        print(f"Pool Name: {overview['pool']['pool_name']}")
        print(f"Members: {overview['pool']['active_members']}/{overview['pool']['total_members']}")
        print(f"Total Capital: ${overview['pool']['total_capital']:.2f}")
        print(f"Pool Balance: ${overview['pool']['pool_balance']:.2f}")
        print(f"ROI: {overview['pool']['roi_percentage']:.2f}%")
        print(f"\nInsurance Reserve: ${overview['insurance']['reserve_balance']:.2f}")
        print(f"Total Claims Paid: ${overview['insurance']['total_paid']:.2f}")
        print(f"\nValidators Active: {overview['validators']['active_validators']}")
        print(f"Approved Trades: {overview['validators']['approved_trades']}")
        print(f"Pending Trades: {overview['validators']['pending_trades']}")
        print(f"\nEnabled Products: {overview['products']['enabled_products']}")
        print(f"Total Profit Generated: ${overview['total_profit_generated']:.2f}")
        print(f"Total Trades Executed: {overview['total_trades_executed']}")
        print("="*70 + "\n")


def main():
    """Main entry point"""
    try:
        # Initialize pool bot
        pool = PoolBot("Arbitrage Trading Pool", max_members=100, min_contribution=100)
        
        # Add validators
        pool.add_validator("validator_1", "LEAD", "0x123...")
        pool.add_validator("validator_2", "SENIOR", "0x456...")
        
        # Add pool members
        pool.add_pool_member("member_1_address", 1000)
        pool.add_pool_member("member_2_address", 2000)
        pool.add_pool_member("member_3_address", 5000)
        
        # Print initial status
        pool.print_pool_summary()
        
        # Run arbitrage product
        print("Executing arbitrage product...")
        result = pool.execute_arbitrage_product()
        print(f"Result: {result}")
        
        # Print final status
        pool.print_pool_summary()
        
        # Show member status
        print("\nMember Details:")
        for member_addr in ["member_1_address", "member_2_address", "member_3_address"]:
            status = pool.get_member_status(member_addr)
            print(f"{member_addr}: {status}")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
