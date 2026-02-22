"""Product and Service Registry - Extensible framework for multiple bot strategies"""

import logging
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """Represents a tradeable product/service"""
    product_id: str
    name: str
    description: str
    category: str  # 'arbitrage', 'staking', 'trading', 'lending', etc.
    enabled: bool
    config: Dict
    handler_function: Optional[Callable] = None
    created_date: datetime = None
    
    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'product_id': self.product_id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'enabled': self.enabled,
            'config': self.config,
            'created_date': self.created_date.isoformat(),
        }


class ProductRegistry:
    """
    Registry for managing multiple products/services
    Allows extensible additions of new trading strategies
    """
    
    def __init__(self):
        """Initialize product registry"""
        self.products: Dict[str, Product] = {}
        self.handlers: Dict[str, Callable] = {}
        logger.info("Product registry initialized")
    
    def register_product(self, product: Product, handler: Optional[Callable] = None) -> bool:
        """
        Register a new product/service
        
        Args:
            product: Product instance
            handler: Function to execute for this product
            
        Returns:
            True if registered successfully
        """
        try:
            if product.product_id in self.products:
                logger.warning(f"Product {product.product_id} already exists")
                return False
            
            self.products[product.product_id] = product
            
            if handler:
                self.handlers[product.product_id] = handler
            
            logger.info(f"Product registered: {product.name} ({product.product_id})")
            return True
        
        except Exception as e:
            logger.error(f"Error registering product: {e}")
            return False
    
    def enable_product(self, product_id: str) -> bool:
        """Enable a product"""
        try:
            if product_id not in self.products:
                logger.warning(f"Product {product_id} not found")
                return False
            
            self.products[product_id].enabled = True
            logger.info(f"Product {product_id} enabled")
            return True
        
        except Exception as e:
            logger.error(f"Error enabling product: {e}")
            return False
    
    def disable_product(self, product_id: str) -> bool:
        """Disable a product"""
        try:
            if product_id not in self.products:
                logger.warning(f"Product {product_id} not found")
                return False
            
            self.products[product_id].enabled = False
            logger.info(f"Product {product_id} disabled")
            return True
        
        except Exception as e:
            logger.error(f"Error disabling product: {e}")
            return False
    
    def execute_product(self, product_id: str, *args, **kwargs) -> Optional[Any]:
        """
        Execute a product's handler
        
        Args:
            product_id: Product to execute
            *args: Arguments for handler
            **kwargs: Keyword arguments for handler
            
        Returns:
            Result from handler
        """
        try:
            if product_id not in self.products:
                logger.warning(f"Product {product_id} not found")
                return None
            
            product = self.products[product_id]
            
            if not product.enabled:
                logger.warning(f"Product {product_id} is disabled")
                return None
            
            if product_id not in self.handlers:
                logger.warning(f"No handler for product {product_id}")
                return None
            
            handler = self.handlers[product_id]
            result = handler(*args, **kwargs)
            
            logger.info(f"Product {product_id} executed successfully")
            return result
        
        except Exception as e:
            logger.error(f"Error executing product {product_id}: {e}")
            return None
    
    def get_enabled_products(self, category: str = None) -> List[Product]:
        """
        Get enabled products, optionally filtered by category
        
        Args:
            category: Optional category filter
            
        Returns:
            List of enabled products
        """
        products = [p for p in self.products.values() if p.enabled]
        
        if category:
            products = [p for p in products if p.category == category]
        
        return products
    
    def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID"""
        return self.products.get(product_id)
    
    def get_all_products(self) -> List[Dict]:
        """Get all products"""
        return [p.to_dict() for p in self.products.values()]
    
    def get_products_by_category(self, category: str) -> List[Dict]:
        """Get products by category"""
        return [p.to_dict() for p in self.products.values() if p.category == category]
    
    def get_registry_stats(self) -> Dict:
        """Get registry statistics"""
        all_products = list(self.products.values())
        enabled_products = [p for p in all_products if p.enabled]
        
        return {
            'total_products': len(all_products),
            'enabled_products': len(enabled_products),
            'disabled_products': len(all_products) - len(enabled_products),
            'categories': list(set(p.category for p in all_products)),
            'products_by_category': {
                cat: len([p for p in all_products if p.category == cat])
                for cat in set(p.category for p in all_products)
            },
            'products': self.get_all_products(),
        }
