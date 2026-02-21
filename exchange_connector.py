"""Exchange API connectors for real-time price fetching"""

import ccxt
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ExchangeConnector:
    """Base class for exchange connections"""
    
    def __init__(self, exchange_name: str, api_key: str, api_secret: str, **kwargs):
        """
        Initialize exchange connector
        
        Args:
            exchange_name: Name of exchange (binance, coinbase, kraken)
            api_key: Exchange API key
            api_secret: Exchange API secret
            **kwargs: Additional parameters (e.g., passphrase for Coinbase)
        """
        self.exchange_name = exchange_name
        self.exchange = self._create_exchange(exchange_name, api_key, api_secret, **kwargs)
        self.last_update = None
        
    def _create_exchange(self, exchange_name: str, api_key: str, api_secret: str, **kwargs):
        """Create CCXT exchange instance"""
        exchange_class = getattr(ccxt, exchange_name)
        config = {
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        }
        config.update(kwargs)
        
        exchange = exchange_class(config)
        logger.info(f"Connected to {exchange_name}")
        return exchange
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a trading pair
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USD')
            
        Returns:
            Current price or None if error
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            self.last_update = datetime.now()
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching price for {symbol} on {self.exchange_name}: {e}")
            return None
    
    def get_order_book(self, symbol: str, limit: int = 5) -> Optional[Dict]:
        """
        Get order book for a symbol
        
        Args:
            symbol: Trading pair
            limit: Number of orders to fetch
            
        Returns:
            Order book data or None
        """
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
            return {
                'bids': orderbook['bids'],
                'asks': orderbook['asks'],
                'timestamp': orderbook['timestamp']
            }
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return None
    
    def get_balance(self) -> Optional[Dict]:
        """
        Get account balance
        
        Returns:
            Balance dictionary or None
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return None
    
    def execute_buy_order(self, symbol: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        """
        Execute a buy order
        
        Args:
            symbol: Trading pair
            amount: Amount to buy
            price: Limit price (None for market order)
            
        Returns:
            Order details or None
        """
        try:
            if price:
                order = self.exchange.create_limit_buy_order(symbol, amount, price)
            else:
                order = self.exchange.create_market_buy_order(symbol, amount)
            
            logger.info(f"Buy order placed on {self.exchange_name}: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"Error executing buy order: {e}")
            return None
    
    def execute_sell_order(self, symbol: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        """
        Execute a sell order
        
        Args:
            symbol: Trading pair
            amount: Amount to sell
            price: Limit price (None for market order)
            
        Returns:
            Order details or None
        """
        try:
            if price:
                order = self.exchange.create_limit_sell_order(symbol, amount, price)
            else:
                order = self.exchange.create_market_sell_order(symbol, amount)
            
            logger.info(f"Sell order placed on {self.exchange_name}: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"Error executing sell order: {e}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False


class MultiExchangeManager:
    """Manages multiple exchange connections"""
    
    def __init__(self, exchanges_config: Dict):
        """
        Initialize manager with multiple exchange configs
        
        Args:
            exchanges_config: Dictionary of exchange configurations
        """
        self.exchanges = {}
        self._initialize_exchanges(exchanges_config)
    
    def _initialize_exchanges(self, exchanges_config: Dict):
        """Initialize all exchange connectors"""
        for exchange_name, config in exchanges_config.items():
            try:
                connector = ExchangeConnector(
                    exchange_name,
                    config.get('api_key'),
                    config.get('api_secret'),
                    **{k: v for k, v in config.items() if k not in ['api_key', 'api_secret', 'base_url']}
                )
                self.exchanges[exchange_name] = connector
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_name}: {e}")
    
    def get_prices(self, symbol: str) -> Dict[str, Optional[float]]:
        """
        Get prices from all exchanges
        
        Args:
            symbol: Trading pair
            
        Returns:
            Dictionary of exchange -> price
        """
        prices = {}
        for exchange_name, connector in self.exchanges.items():
            prices[exchange_name] = connector.get_price(symbol)
        return prices
    
    def find_arbitrage_opportunity(self, symbol: str, min_profit: float = 0.5) -> Optional[Tuple]:
        """
        Find arbitrage opportunity across exchanges
        
        Args:
            symbol: Trading pair
            min_profit: Minimum profit percentage to consider
            
        Returns:
            Tuple of (buy_exchange, buy_price, sell_exchange, sell_price, profit_pct)
        """
        prices = self.get_prices(symbol)
        valid_prices = {k: v for k, v in prices.items() if v is not None}
        
        if len(valid_prices) < 2:
            return None
        
        min_price_exchange = min(valid_prices, key=valid_prices.get)
        max_price_exchange = max(valid_prices, key=valid_prices.get)
        
        min_price = valid_prices[min_price_exchange]
        max_price = valid_prices[max_price_exchange]
        
        profit_pct = ((max_price - min_price) / min_price) * 100
        
        if profit_pct >= min_profit:
            return (min_price_exchange, min_price, max_price_exchange, max_price, profit_pct)
        
        return None
