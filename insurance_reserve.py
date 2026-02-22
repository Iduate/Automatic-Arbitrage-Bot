"""Insurance Reserve System - Protects pool funds from losses"""

import logging
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InsuranceClaim:
    """Represents an insurance claim"""
    claim_id: str
    member_address: str
    loss_amount: float
    reason: str
    status: str  # 'pending', 'approved', 'denied', 'paid'
    claim_date: datetime
    payout_amount: float = 0


class InsuranceReserve:
    """
    Manages insurance reserve for pool protection
    Covers unexpected losses, failed trades, etc.
    """
    
    def __init__(self, initial_reserve: float = 0, reserve_percentage: float = 5):
        """
        Initialize insurance reserve
        
        Args:
            initial_reserve: Initial reserve amount
            reserve_percentage: Percentage of pool profits to allocate to reserve (5% = 0.05)
        """
        self.reserve_balance = initial_reserve
        self.reserve_percentage = reserve_percentage
        self.total_reserves_allocated = initial_reserve
        self.total_claims_paid = 0
        self.claims: Dict[str, InsuranceClaim] = {}
        self.created_date = datetime.now()
        
        logger.info(f"Insurance reserve initialized with ${initial_reserve}")
    
    def allocate_profit_to_reserve(self, profit_amount: float) -> float:
        """
        Automatically allocate a portion of profits to reserve
        
        Args:
            profit_amount: Total profit generated
            
        Returns:
            Amount allocated to reserve
        """
        try:
            allocation = profit_amount * self.reserve_percentage
            self.reserve_balance += allocation
            self.total_reserves_allocated += allocation
            
            logger.info(f"Allocated ${allocation} to insurance reserve (balance: ${self.reserve_balance})")
            return allocation
        
        except Exception as e:
            logger.error(f"Error allocating to reserve: {e}")
            return 0
    
    def file_claim(self, claim_id: str, member_address: str, loss_amount: float, reason: str = "") -> bool:
        """
        File an insurance claim
        
        Args:
            claim_id: Unique claim ID
            member_address: Member filing claim
            loss_amount: Amount of loss
            reason: Reason for claim
            
        Returns:
            True if claim filed successfully
        """
        try:
            if claim_id in self.claims:
                logger.warning(f"Claim {claim_id} already exists")
                return False
            
            claim = InsuranceClaim(
                claim_id=claim_id,
                member_address=member_address,
                loss_amount=loss_amount,
                reason=reason,
                status='pending',
                claim_date=datetime.now(),
            )
            
            self.claims[claim_id] = claim
            logger.info(f"Claim {claim_id} filed by {member_address} for ${loss_amount}")
            return True
        
        except Exception as e:
            logger.error(f"Error filing claim: {e}")
            return False
    
    def approve_claim(self, claim_id: str, payout_percentage: float = 100) -> bool:
        """
        Approve and pay a claim
        
        Args:
            claim_id: Claim to approve
            payout_percentage: Percentage of claim to pay (0-100)
            
        Returns:
            True if approved successfully
        """
        try:
            if claim_id not in self.claims:
                logger.warning(f"Claim {claim_id} not found")
                return False
            
            claim = self.claims[claim_id]
            
            if claim.status != 'pending':
                logger.warning(f"Claim {claim_id} is not pending")
                return False
            
            # Calculate payout
            payout = claim.loss_amount * (payout_percentage / 100)
            
            # Check reserve balance
            if payout > self.reserve_balance:
                logger.warning(f"Insufficient reserve balance. Required: ${payout}, Available: ${self.reserve_balance}")
                payout = self.reserve_balance
            
            # Process payout
            claim.status = 'approved'
            claim.payout_amount = payout
            self.reserve_balance -= payout
            self.total_claims_paid += payout
            
            logger.info(f"Claim {claim_id} approved for ${payout} payout")
            return True
        
        except Exception as e:
            logger.error(f"Error approving claim: {e}")
            return False
    
    def deny_claim(self, claim_id: str, reason: str = "") -> bool:
        """
        Deny a claim
        
        Args:
            claim_id: Claim to deny
            reason: Reason for denial
            
        Returns:
            True if denied successfully
        """
        try:
            if claim_id not in self.claims:
                logger.warning(f"Claim {claim_id} not found")
                return False
            
            claim = self.claims[claim_id]
            claim.status = 'denied'
            
            logger.info(f"Claim {claim_id} denied. Reason: {reason}")
            return True
        
        except Exception as e:
            logger.error(f"Error denying claim: {e}")
            return False
    
    def get_reserve_health(self) -> Dict:
        """Get insurance reserve health status"""
        try:
            pending_claims = len([c for c in self.claims.values() if c.status == 'pending'])
            pending_amount = sum(c.loss_amount for c in self.claims.values() if c.status == 'pending')
            
            return {
                'reserve_balance': self.reserve_balance,
                'total_allocated': self.total_reserves_allocated,
                'total_paid': self.total_claims_paid,
                'pending_claims': pending_claims,
                'pending_amount': pending_amount,
                'coverage_ratio': self.reserve_balance / pending_amount if pending_amount > 0 else float('inf'),
                'claim_approval_rate': (len([c for c in self.claims.values() if c.status == 'approved']) / len(self.claims) * 100) if self.claims else 0,
            }
        
        except Exception as e:
            logger.error(f"Error getting reserve health: {e}")
            return {}
    
    def get_claims_history(self, status_filter: str = None) -> Dict:
        """
        Get claims history
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            Dictionary of claims
        """
        claims = dict(self.claims)
        
        if status_filter:
            claims = {k: v for k, v in claims.items() if v.status == status_filter}
        
        return {k: {
            'claim_id': v.claim_id,
            'member_address': v.member_address,
            'loss_amount': v.loss_amount,
            'payout_amount': v.payout_amount,
            'status': v.status,
            'reason': v.reason,
            'claim_date': v.claim_date.isoformat(),
        } for k, v in claims.items()}
