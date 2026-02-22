"""Smart Contract Pool Interface for DeFi pooling system"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PoolMember:
    """Represents a pool member"""
    address: str
    capital_contributed: float
    shares_owned: float
    joined_date: datetime
    status: str  # 'active', 'inactive', 'withdrawn'
    
    def to_dict(self) -> Dict:
        return {
            'address': self.address,
            'capital_contributed': self.capital_contributed,
            'shares_owned': self.shares_owned,
            'joined_date': self.joined_date.isoformat(),
            'status': self.status,
        }


class PoolSmartContract:
    """
    Manages the DeFi pool smart contract
    Handles member contributions, withdrawals, and profit distribution
    """
    
    def __init__(self, pool_name: str, max_members: int = None, min_contribution: float = 100):
        """
        Initialize pool smart contract
        
        Args:
            pool_name: Name of the pool
            max_members: Maximum members (None for unlimited)
            min_contribution: Minimum capital to contribute
        """
        self.pool_name = pool_name
        self.max_members = max_members
        self.min_contribution = min_contribution
        
        self.members: Dict[str, PoolMember] = {}
        self.total_capital = 0
        self.total_shares = 0
        self.pool_balance = 0
        self.created_date = datetime.now()
        
        logger.info(f"Pool contract initialized: {pool_name}")
    
    def add_member(self, address: str, capital: float) -> bool:
        """
        Add a new member to the pool
        
        Args:
            address: Member wallet address
            capital: Capital to contribute
            
        Returns:
            True if added successfully
        """
        try:
            # Validation
            if address in self.members:
                logger.warning(f"Member {address} already exists")
                return False
            
            if capital < self.min_contribution:
                logger.warning(f"Capital ${capital} below minimum ${self.min_contribution}")
                return False
            
            if self.max_members and len(self.members) >= self.max_members:
                logger.warning(f"Pool at maximum capacity ({self.max_members} members)")
                return False
            
            # Calculate shares (1:1 initially)
            shares = capital
            
            # Create member
            member = PoolMember(
                address=address,
                capital_contributed=capital,
                shares_owned=shares,
                joined_date=datetime.now(),
                status='active'
            )
            
            self.members[address] = member
            self.total_capital += capital
            self.total_shares += shares
            self.pool_balance += capital
            
            logger.info(f"Member {address} added with ${capital} capital and {shares} shares")
            return True
        
        except Exception as e:
            logger.error(f"Error adding member: {e}")
            return False
    
    def remove_member(self, address: str) -> bool:
        """
        Remove member from pool (withdraw capital)
        
        Args:
            address: Member wallet address
            
        Returns:
            True if removed successfully
        """
        try:
            if address not in self.members:
                logger.warning(f"Member {address} not found")
                return False
            
            member = self.members[address]
            
            # Calculate withdrawal amount based on current share value
            share_value = self.pool_balance / self.total_shares if self.total_shares > 0 else 0
            withdrawal_amount = member.shares_owned * share_value
            
            # Update member
            member.status = 'withdrawn'
            
            # Update pool
            self.total_capital -= member.capital_contributed
            self.total_shares -= member.shares_owned
            self.pool_balance -= withdrawal_amount
            
            logger.info(f"Member {address} withdrawn with ${withdrawal_amount}")
            return True
        
        except Exception as e:
            logger.error(f"Error removing member: {e}")
            return False
    
    def distribute_profit(self, profit_amount: float) -> Dict[str, float]:
        """
        Distribute profit among members based on shares
        
        Args:
            profit_amount: Total profit to distribute
            
        Returns:
            Dictionary of member address -> distributed profit
        """
        try:
            distribution = {}
            
            if self.total_shares == 0:
                logger.warning("No shares to distribute profit")
                return distribution
            
            for address, member in self.members.items():
                if member.status == 'active':
                    # Distribute based on share ownership percentage
                    share_percentage = member.shares_owned / self.total_shares
                    member_profit = profit_amount * share_percentage
                    distribution[address] = member_profit
                    
                    # Update pool balance
                    self.pool_balance += member_profit
            
            logger.info(f"Distributed ${profit_amount} profit among {len([m for m in self.members.values() if m.status == 'active'])} members")
            return distribution
        
        except Exception as e:
            logger.error(f"Error distributing profit: {e}")
            return {}
    
    def get_member_balance(self, address: str) -> Optional[float]:
        """
        Get member's current balance (capital + share of profits)
        
        Args:
            address: Member wallet address
            
        Returns:
            Member balance or None
        """
        try:
            if address not in self.members:
                return None
            
            member = self.members[address]
            share_value = self.pool_balance / self.total_shares if self.total_shares > 0 else 0
            balance = member.shares_owned * share_value
            
            return balance
        
        except Exception as e:
            logger.error(f"Error getting member balance: {e}")
            return None
    
    def get_pool_stats(self) -> Dict:
        """Get pool statistics"""
        try:
            active_members = len([m for m in self.members.values() if m.status == 'active'])
            share_value = self.pool_balance / self.total_shares if self.total_shares > 0 else 0
            
            return {
                'pool_name': self.pool_name,
                'total_members': len(self.members),
                'active_members': active_members,
                'total_capital': self.total_capital,
                'total_shares': self.total_shares,
                'pool_balance': self.pool_balance,
                'share_value': share_value,
                'profit_generated': self.pool_balance - self.total_capital,
                'roi_percentage': ((self.pool_balance - self.total_capital) / self.total_capital * 100) if self.total_capital > 0 else 0,
                'member_limit': self.max_members,
                'min_contribution': self.min_contribution,
                'created_date': self.created_date.isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error getting pool stats: {e}")
            return {}
    
    def get_all_members(self) -> List[Dict]:
        """Get all members"""
        return [member.to_dict() for member in self.members.values()]
