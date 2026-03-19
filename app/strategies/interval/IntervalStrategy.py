import asyncio
import logging
from datetime import datetime, timedelta, time as dt_time
from typing import List, Optional, Set
from uuid import uuid4

import numpy as np
from tinkoff.invest import CandleInterval, HistoricCandle, AioRequestError, Instrument
from tinkoff.invest.grpc.instruments_pb2 import INSTRUMENT_ID_TYPE_FIGI
from tinkoff.invest.grpc.orders_pb2 import (
    ORDER_DIRECTION_SELL,
    ORDER_DIRECTION_BUY,
    ORDER_TYPE_MARKET,
)
from tinkoff.invest.utils import now

from app.client import client
from app.settings import settings
from app.stats.handler import StatsHandler
from app.strategies.interval.models import IntervalStrategyConfig, Corridor
from app.strategies.base import BaseStrategy
from app.strategies.models import StrategyName
from app.utils.portfolio import get_position, get_order
from app.utils.quantity import is_quantity_valid
from app.utils.quotation import quotation_to_float

logger = logging.getLogger(__name__)


class IntervalStrategy(BaseStrategy):
    """
    Interval strategy.

    Main strategy logic is to buy at the lowest price and sell at the highest price of the
    calculated interval.

    Interval is calculated by taking interval_size percents of the last prices
    for the last days_back_to_consider days. By default, it's set to 80 percents which means
    that the interval is from 10th to 90th percentile.
    """

    def __init__(self, figi: str, **kwargs):
        self.account_id = settings.account_id
        self.corridor: Optional[Corridor] = None
        self.figi = figi
        self.instrument_info: Optional[Instrument] = None
        self.config: IntervalStrategyConfig = IntervalStrategyConfig(**kwargs)
        self.stats_handler = StatsHandler(StrategyName.INTERVAL, client)
        self.stop_loss_triggered_today: Set[str] = set()
     
    async def get_historical_data(self) -> List[HistoricCandle]:
        """
        Gets historical data for the instrument. Returns list of candles.
        Requests all the 1-min candles from days_back_to_consider days back to now.

        :return: list of HistoricCandle
        """
        candles = []
        logger.debug(
            f"Start getting historical data for {self.config.days_back_to_consider} "
            f"days back from now. figi={self.figi}"
        )
        async for candle in client.get_all_candles(
            figi=self.figi,
            from_=now() - timedelta(days=self.config.days_back_to_consider),
            to=now(),
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
        ):
            candles.append(candle)
        logger.debug(f"Found {len(candles)} candles. {self.instrument_info.name}")
        return candles

    async def update_corridor(self) -> None:
        """
        Gets historical data and calculates new corridor. Stores it in the class.
        """
        candles = await self.get_historical_data()
        if len(candles) == 0:
            return
        values = []
        for candle in candles:
            values.append(quotation_to_float(candle.close))
        lower_percentile = (1 - self.config.interval_size) / 2 * 100
        corridor = list(np.percentile(values, [lower_percentile, 100 - lower_percentile]))
        logger.debug(
            f"Corridor: {corridor}. days_back_to_consider={self.config.days_back_to_consider} "
            f"figi={self.instrument_info.name}"
        )
        self.corridor = Corridor(bottom=corridor[0], top=corridor[1])

    async def get_position_quantity(self) -> int:
        """
        Get quantity of the instrument in the position.
        :return: int - quantity
        """
        positions = (await client.get_portfolio(account_id=self.account_id)).positions
        position = get_position(positions, self.figi)
        if position is None:
            return 0
        return int(quotation_to_float(position.quantity))

    async def handle_corridor_crossing_top(self, last_price: float) -> None:
        """
        This method is called when last price is higher than top corridor border.
        Check how many shares we already have and sell them.

        :param last_price: last price of the instrument
        """
        position_quantity = await self.get_position_quantity()
        if abs(position_quantity) < self.config.quantity_limit or position_quantity > 0:
            quantity_to_sell = self.config.quantity_limit + position_quantity
            logger.info(
                f"\033[91mSelling {quantity_to_sell} shares. Last price={last_price} {self.instrument_info.name}\033[0m"
            )
            try:
                quantity = quantity_to_sell / self.instrument_info.lot
                if not is_quantity_valid(quantity):
                    raise ValueError(f"Invalid quantity for posting an order. quantity={quantity}")
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    figi=self.figi,
                    direction=ORDER_DIRECTION_SELL,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                )
            except Exception as e:
                logger.error(f"Failed to post sell order. {self.instrument_info.name}. {e}")
                return
            asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )
            # Calculate take profit level after entering position
           
        else: 
            logger.info(
                f"Already have a position {position_quantity} shares. {self.instrument_info.name}"
            )
    async def handle_corridor_crossing_bottom(self, last_price: float) -> None:
        """
        This method is called when last price is lower than bottom corridor border.
        Check how many shares we already have and buy more until the quantity_limit is reached.

        :param last_price: last price of the instrument
        """
        position_quantity = await self.get_position_quantity()
        if abs(position_quantity) < self.config.quantity_limit or position_quantity < 0:
            quantity_to_buy = self.config.quantity_limit - position_quantity
            logger.info(
                f"\033[92mBuying {quantity_to_buy} shares. Last price={last_price} {self.instrument_info.name}\033[0m"
            )
            try:
                quantity = quantity_to_buy / self.instrument_info.lot
                if not is_quantity_valid(quantity):
                    raise ValueError(f"Invalid quantity for posting an order. quantity={quantity}")
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    figi=self.figi,
                    direction=ORDER_DIRECTION_BUY,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                )
            except Exception as e:
                logger.error(f"Failed to post buy order. {self.instrument_info.name}. {e}")
                return
            asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )
            # Calculate take profit level after entering position
        
        else: 
            logger.info(
                f"Already have a position {position_quantity} shares. {self.instrument_info.name}"
            )            

    async def get_last_price(self) -> float:
        """
        Get last price of the instrument.
        :return: float - last price
        """
        last_prices_response = await client.get_last_prices(figi=[self.figi])
        last_prices = last_prices_response.last_prices
        return quotation_to_float(last_prices.pop().price)

    async def close_all_positions(self) -> None:
        """
        Close all open positions for the account.
        For long positions (quantity > 0): sell to close.
        For short positions (quantity < 0): buy to cover and return to zero.
        Clears stop_loss_triggered_today set at the end of day.
        """
        position_quantity = await self.get_position_quantity()
        if position_quantity == 0:
            logger.info("No open positions to close.")
        
        # Clear stop_loss_triggered_today set at the end of day (23:00 Moscow time)
        logger.info(f"Clearing stop_loss_triggered_today set for {self.instrument_info.name}")
        self.stop_loss_triggered_today.clear()
            
        if position_quantity > 0:
            quantity_to_sell = position_quantity
            logger.info(
                f"\033[91mSelling {quantity_to_sell} shares. {self.instrument_info.name}\033[0m"
            )
            try:
                quantity = quantity_to_sell / self.instrument_info.lot
                if not is_quantity_valid(quantity):
                    raise ValueError(f"Invalid quantity for posting an order. quantity={quantity}")
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    figi=self.figi,
                    direction=ORDER_DIRECTION_SELL,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                )
            except Exception as e:
                logger.error(f"Failed to post sell order. {self.instrument_info.name}. {e}")
                return
            asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )  

        if position_quantity < 0:
            quantity_to_buy = abs(position_quantity)
            logger.info(
                f"\033[92mBuying {quantity_to_buy} shares. {self.instrument_info.name}\033[0m"
            )
            try:
                quantity = quantity_to_buy / self.instrument_info.lot
                if not is_quantity_valid(quantity):
                    raise ValueError(f"Invalid quantity for posting an order. quantity={quantity}")
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    figi=self.figi,
                    direction=ORDER_DIRECTION_BUY,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                )
            except Exception as e:
                logger.error(f"Failed to post buy order. {self.instrument_info.name}. {e}")
                return
            asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )
        return

    async def validate_stop_loss(self, last_price: float) -> None:
        """
        Check if stop loss is reached. If yes, then closes the position.
        For long positions (quantity > 0): sells when price drops below threshold.
        For short positions (quantity < 0): buys to cover when price rises above threshold.
        :param last_price: Last price of the instrument.
        """
        positions = (await client.get_portfolio(account_id=self.account_id)).positions
        position = get_position(positions, self.figi)
        if position is None or quotation_to_float(position.quantity) == 0:
            return
        
        quantity = quotation_to_float(position.quantity)
        position_price = quotation_to_float(position.average_position_price)
        
        should_close = False
        direction = None
        logger.info(f"Stop loss check. Last price={last_price}. Position price={position_price}. Quantity={quantity}. Stop long price {position_price - position_price * self.config.stop_loss_percent}. Stop short price {position_price + position_price * self.config.stop_loss_percent}. {self.instrument_info.name}")
        if position_price != 0:
            if quantity > 0:
                # Long position: stop loss when price drops
                if last_price <= position_price - position_price * self.config.stop_loss_percent:
                    should_close = True
                    direction = ORDER_DIRECTION_SELL
            elif quantity < 0:
                # Short position: stop loss when price rises
                if last_price >= position_price + position_price * self.config.stop_loss_percent:
                    should_close = True
                    direction = ORDER_DIRECTION_BUY
            
        if not should_close:
            return
            
        # Add figi to stop_loss_triggered_today set to prevent re-processing
        self.stop_loss_triggered_today.add(self.figi)
        
        # Calculate profit/loss without commission
        if quantity > 0:
            # Long position: profit = (last_price - position_price) * quantity
            pnl = (last_price - position_price) * quantity
        else:
            # Short position: profit = (position_price - last_price) * abs(quantity)
            pnl = (position_price - last_price) * abs(quantity)
        
        direction_color = "\033[91m" if direction == ORDER_DIRECTION_SELL else "\033[92m"
        logger.info(f"{direction_color}Stop loss triggered. Last price={last_price}. Position price={position_price}. Stop loss price={position_price + position_price * self.config.stop_loss_percent}. PnL={pnl:.2f} {self.instrument_info.currency}.  {self.instrument_info.name}\033[0m")
        try:
            quantity_to_trade = int(abs(quantity)) / self.instrument_info.lot
            if not is_quantity_valid(quantity_to_trade):
                raise ValueError(f"Invalid quantity for posting an order. quantity={quantity_to_trade}")
            posted_order = await client.post_order(
                order_id=str(uuid4()),
                figi=self.figi,
                direction=direction,
                quantity=int(quantity_to_trade),
                order_type=ORDER_TYPE_MARKET,
                account_id=self.account_id,
            )
        except Exception as e:
            logger.error(f"Failed to post {direction} order. {self.instrument_info.name}. {e}")
            return
        asyncio.create_task(
            self.stats_handler.handle_new_order(
                order_id=posted_order.order_id, account_id=self.account_id
            )
        )
        return

    async def validate_take_profit(self, last_price: float) -> None:
        """
        Check if take profit is reached. If yes, then closes the position.
        Take profit is triggered when price reaches the midpoint of the corridor from entry price.
        
        For long positions (quantity > 0): sells when price reaches or exceeds the take profit level.
        For short positions (quantity < 0): buys to cover when price reaches or falls below the take profit level.
                
        :param last_price: Last price of the instrument.
        """
                   
        positions = (await client.get_portfolio(account_id=self.account_id)).positions
        position = get_position(positions, self.figi)
        
        if position is None or quotation_to_float(position.quantity) == 0:
            # Position closed, reset take profit price
            return
        
        quantity = quotation_to_float(position.quantity)
        position_price = quotation_to_float(position.average_position_price)
        
        should_close = False
        direction = None
        
        logger.info(f"Take profit check. Last price={last_price} Target price={(self.corridor.top + self.corridor.bottom) / 2}  {self.instrument_info.name}")
        if position_price != 0:
            if quantity > 0:
                target_price = position_price * 1.001 #(self.corridor.top + self.corridor.bottom) / 2
                # Long position: take profit when price reaches or exceeds target
                if last_price >= target_price:
                    should_close = True
                    direction = ORDER_DIRECTION_SELL
            elif quantity < 0:
                target_price = position_price / 1.001 #(self.corridor.top + self.corridor.bottom) / 2
                # Short position: take profit when price reaches or falls below target
                if last_price <= target_price: 
                    should_close = True
                    direction = ORDER_DIRECTION_BUY
        
        if not should_close:
            return
            
        # Calculate profit/loss without commission
        if quantity > 0:
            # Long position: profit = (last_price - position_price) * quantity
            pnl = (last_price - position_price) * quantity
        else:
            # Short position: profit = (position_price - last_price) * abs(quantity)
            pnl = (position_price - last_price) * abs(quantity)
        
        direction_color = "\033[91m" if direction == ORDER_DIRECTION_SELL else "\033[92m"
        logger.info(f"{direction_color}Take profit triggered. Last price={last_price}, target={target_price} PnL={pnl:.2f} {self.instrument_info.currency}. {self.instrument_info.name}\033[0m")
        try:
            quantity_to_trade = int(abs(quantity)) / self.instrument_info.lot
            if not is_quantity_valid(quantity_to_trade):
                raise ValueError(f"Invalid quantity for posting an order. quantity={quantity_to_trade}")
            posted_order = await client.post_order(
                order_id=str(uuid4()),
                figi=self.figi,
                direction=direction,
                quantity=int(quantity_to_trade),
                order_type=ORDER_TYPE_MARKET,
                account_id=self.account_id,
            )
        except Exception as e:
            logger.error(f"Failed to post {direction} order. {self.instrument_info.name}. {e}")
            return
        asyncio.create_task(
            self.stats_handler.handle_new_order(
                order_id=posted_order.order_id, account_id=self.account_id
            )
        )
        return

    async def ensure_market_open(self):
        """
        Ensure that the market is open. Holds the loop until the instrument is available.
        :return: when instrument is available for trading
        """
        trading_status = await client.get_trading_status(figi=self.figi)
        while not (
            trading_status.market_order_available_flag and trading_status.api_trade_available_flag
        ):
            logger.debug(f"Waiting for the market to open. figi={self.figi}")
            await asyncio.sleep(60)
            trading_status = await client.get_trading_status(figi=self.figi)

    async def prepare_data(self):
        self.instrument_info = (
            await client.get_instrument(id_type=INSTRUMENT_ID_TYPE_FIGI, id=self.figi)
        ).instrument

    async def main_cycle(self):
        await self.prepare_data()
        logger.info(
            f"Starting interval strategy for figi {self.figi} "
            f"({self.instrument_info.name} {self.instrument_info.currency}) lot size is {self.instrument_info.lot}. "
            f"Configuration is: {self.config}"
        )
        
                
        while True:
            try:
                current_time = now()
                    
                moscow_hour = current_time.hour+3
                moscow_minute = current_time.minute
                #logger.info(moscow_hour)
                #logger.info(moscow_minute)
                    
                if moscow_hour >= 23:

                    logger.info("Time to close all positions (23:00 Moscow time)")
                    await self.close_all_positions()
                    # Reset take profit price when closing positions at end of day
                    
                else:

                    if self.figi in self.stop_loss_triggered_today:
                        logger.debug(f"Stop loss already triggered for {self.instrument_info.name} today. Skipping.")
                    else:
                        await self.ensure_market_open()
                        await self.update_corridor()

                        orders = await client.get_orders(account_id=self.account_id)
                        if get_order(orders=orders.orders, figi=self.figi):
                            logger.info(f"There are orders in progress. Waiting. figi={self.instrument_info.name}")
                            await asyncio.sleep(self.config.check_interval)
                            continue

                        last_price = await self.get_last_price()
                        logger.debug(f"Last price: {last_price}, figi={self.instrument_info.name}")
                                        
                        
                        if last_price >= self.corridor.top:
                            logger.debug(
                                f"Last price {last_price} is higher than top corridor border "
                                f"{self.corridor.top}. {self.instrument_info.name}"
                            )
                            await self.handle_corridor_crossing_top(last_price=last_price)
                        elif last_price <= self.corridor.bottom:
                            logger.debug(
                                f"Last price {last_price} is lower than bottom corridor border "
                                f"{self.corridor.bottom}. {self.instrument_info.name}"
                            )
                            await self.handle_corridor_crossing_bottom(last_price=last_price)

                        await self.validate_stop_loss(last_price)
                        await self.validate_take_profit(last_price)
            except AioRequestError as are:
                logger.error(f"Client error {are}")
            
            await asyncio.sleep(self.config.check_interval)
            

    async def start(self):
        if self.account_id is None:
            try:
                self.account_id = (await client.get_accounts()).accounts.pop().id
            except AioRequestError as are:
                logger.error(f"Error taking account id. Stopping strategy. {are}")
                return
        await self.main_cycle()
