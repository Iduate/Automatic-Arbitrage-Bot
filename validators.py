"""Validators Module - Approves trades before execution"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ValidatorRole(Enum):
    """Validator role hierarchy"""
    JUNIOR = 1
    SENIOR = 2
    LEAD = 3
    ADMIN = 4


class Validator:
    """Represents a validator in the pool"""
    
    def __init__(self, validator_id: str, role: ValidatorRole, address: str = None):
        """
        Initialize validator
        
        Args:
            validator_id: Unique validator ID
            role: Validator role
            address: Wallet address (optional)
        """
        self.validator_id = validator_id
        self.role = role
        self.address = address
        self.approvals_count = 0
        self.rejections_count = 0
        self.approval_rate = 100.0
        self.active = True
        self.created_date = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'validator_id': self.validator_id,
            'role': self.role.name,
            'address': self.address,
            'approvals': self.approvals_count,
            'rejections': self.rejections_count,
            'approval_rate': self.approval_rate,
            'active': self.active,
        }


class ValidatorNetwork:
    """
    Manages validator network for trade approval
    Multiple validators approve trades before execution
    """
    
    def __init__(self, required_approvals: int = 2, require_lead_approval: bool = True):
        """
        Initialize validator network
        
        Args:
            required_approvals: Number of approvals needed per trade
            require_lead_approval: Must include at least one LEAD validator
        """
        self.validators: Dict[str, Validator] = {}
        self.required_approvals = required_approvals
        self.require_lead_approval = require_lead_approval
        self.pending_trades: Dict[str, Dict] = {}
        self.approved_trades: List[str] = []
        self.rejected_trades: List[str] = []
        
        logger.info(f"Validator network initialized (required_approvals: {required_approvals})")
    
    def add_validator(self, validator: Validator) -> bool:
        """Add a validator to the network"""
        try:
            if validator.validator_id in self.validators:
                logger.warning(f"Validator {validator.validator_id} already exists")
                return False
            
            self.validators[validator.validator_id] = validator
            logger.info(f"Validator {validator.validator_id} added with role {validator.role.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding validator: {e}")
            return False
    
    def remove_validator(self, validator_id: str) -> bool:
        """Remove a validator"""
        try:
            if validator_id not in self.validators:
                logger.warning(f"Validator {validator_id} not found")
                return False
            
            del self.validators[validator_id]
            logger.info(f"Validator {validator_id} removed")
            return True
        
        except Exception as e:
            logger.error(f"Error removing validator: {e}")
            return False
    
    def submit_trade_for_validation(self, trade_id: str, trade_data: Dict) -> bool:
        """
        Submit a trade for validator approval
        
        Args:
            trade_id: Unique trade ID
            trade_data: Trade details (symbol, amount, exchanges, profit, etc.)
            
        Returns:
            True if submitted successfully
        """
        try:
            if trade_id in self.pending_trades:
                logger.warning(f"Trade {trade_id} already submitted")
                return False
            
            self.pending_trades[trade_id] = {
                'trade_data': trade_data,
                'submitted_at': datetime.now(),
                'approvals': {},  # validator_id -> approval_data
                'rejections': {},
                'status': 'pending',
            }
            
            logger.info(f"Trade {trade_id} submitted for validation")
            return True
        
        except Exception as e:
            logger.error(f"Error submitting trade: {e}")
            return False
    
    def approve_trade(self, trade_id: str, validator_id: str, notes: str = "") -> bool:
        """
        Approve a trade
        
        Args:
            trade_id: Trade to approve
            validator_id: Validator approving
            notes: Optional approval notes
            
        Returns:
            True if approved (and approved count reached)
        """
        try:
            if trade_id not in self.pending_trades:
                logger.warning(f"Trade {trade_id} not found")
                return False
            
            if validator_id not in self.validators:
                logger.warning(f"Validator {validator_id} not found")
                return False
            
            validator = self.validators[validator_id]
            trade = self.pending_trades[trade_id]
            
            # Record approval
            trade['approvals'][validator_id] = {
                'approved_at': datetime.now(),
                'notes': notes,
                'role': validator.role.name,
            }
            
            # Update validator stats
            validator.approvals_count += 1
            self._update_validator_approval_rate(validator)
            
            logger.info(f"Trade {trade_id} approved by {validator_id}")
            
            # Check if trade is fully approved
            return self._check_trade_approval_status(trade_id)
        
        except Exception as e:
            logger.error(f"Error approving trade: {e}")
            return False
    
    def reject_trade(self, trade_id: str, validator_id: str, reason: str = "") -> bool:
        """
        Reject a trade
        
        Args:
            trade_id: Trade to reject
            validator_id: Validator rejecting
            reason: Rejection reason
            
        Returns:
            True if rejected
        """
        try:
            if trade_id not in self.pending_trades:
                logger.warning(f"Trade {trade_id} not found")
                return False
            
            if validator_id not in self.validators:
                logger.warning(f"Validator {validator_id} not found")
                return False
            
            validator = self.validators[validator_id]
            trade = self.pending_trades[trade_id]
            
            # Record rejection
            trade['rejections'][validator_id] = {
                'rejected_at': datetime.now(),
                'reason': reason,
                'role': validator.role.name,
            }
            
            # Update validator stats
            validator.rejections_count += 1
            self._update_validator_approval_rate(validator)
            
            # Mark trade as rejected
            trade['status'] = 'rejected'
            self.rejected_trades.append(trade_id)
            
            logger.info(f"Trade {trade_id} rejected by {validator_id}. Reason: {reason}")
            return True
        
        except Exception as e:
            logger.error(f"Error rejecting trade: {e}")
            return False
    
    def _check_trade_approval_status(self, trade_id: str) -> bool:
        """Check if trade has enough approvals"""
        try:
            trade = self.pending_trades[trade_id]
            approvals = trade['approvals']
            
            # Check approval count
            if len(approvals) < self.required_approvals:
                return False
            
            # Check if lead approval required
            if self.require_lead_approval:
                has_lead_approval = any(
                    approval.get('role') in ['LEAD', 'ADMIN']
                    for approval in approvals.values()
                )
                
                if not has_lead_approval:
                    logger.warning(f"Trade {trade_id} needs lead validator approval")
                    return False
            
            # Trade is approved
            trade['status'] = 'approved'
            self.approved_trades.append(trade_id)
            logger.info(f"Trade {trade_id} has all required approvals - READY FOR EXECUTION")
            
            return True
        
        except Exception as e:
            logger.error(f"Error checking approval status: {e}")
            return False
    
    def _update_validator_approval_rate(self, validator: Validator):
        """Update validator's approval rate"""
        try:
            total = validator.approvals_count + validator.rejections_count
            if total > 0:
                validator.approval_rate = (validator.approvals_count / total) * 100
        except Exception as e:
            logger.error(f"Error updating approval rate: {e}")
    
    def get_validator_stats(self) -> Dict:
        """Get network statistics"""
        try:
            total_validators = len(self.validators)
            active_validators = len([v for v in self.validators.values() if v.active])
            
            return {
                'total_validators': total_validators,
                'active_validators': active_validators,
                'pending_trades': len(self.pending_trades),
                'approved_trades': len(self.approved_trades),
                'rejected_trades': len(self.rejected_trades),
                'validators': [v.to_dict() for v in self.validators.values()],
            }
        
        except Exception as e:
            logger.error(f"Error getting validator stats: {e}")
            return {}
    
    def get_pending_trades(self) -> List[Dict]:
        """Get all pending trades awaiting approval"""
        pending = []
        for trade_id, trade in self.pending_trades.items():
            if trade['status'] == 'pending':
                pending.append({
                    'trade_id': trade_id,
                    'trade_data': trade['trade_data'],
                    'approvals_received': len(trade['approvals']),
                    'approvals_needed': self.required_approvals,
                    'submitted_at': trade['submitted_at'].isoformat(),
                })
        
        return pending
