import uuid
import logging
from datetime import timedelta
from typing import List
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
from tinkoff.invest import (
    GetAccountsResponse,
    Account,
    Client,
    GetOrdersResponse,
    GetLastPricesResponse,
    LastPrice,
    PortfolioResponse,
    PortfolioPosition,
    Quotation,
    OrderDirection,
    MoneyValue,
    PostOrderResponse,
    InstrumentResponse,
    Instrument,
)
from tinkoff.invest.utils import now

from app.client import TinkoffClient
from app.settings import settings
from app.strategies.interval.models import IntervalStrategyConfig
from app.utils.quotation import quotation_to_float

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NoMoreDataError(Exception):
    pass


@pytest.fixture
def account_id():
    return "test_id"


@pytest.fixture(scope="session")
def figi() -> str:
    return "BBG004730JJ5"


@pytest.fixture(scope="session")
def comission() -> float:
    return 0.003


@pytest.fixture(scope="session")
def lot() -> int:
    return 100


@pytest.fixture
def instrument_response(figi: str, lot: int) -> InstrumentResponse:
    return InstrumentResponse(instrument=Instrument(figi=figi, lot=lot))


@pytest.fixture
def accounts_response(account_id: str) -> GetAccountsResponse:
    return GetAccountsResponse(accounts=[Account(id=account_id)])


@pytest.fixture
def orders_response(account_id: str) -> GetOrdersResponse:
    return GetOrdersResponse(orders=[])


@pytest.fixture
def get_portfolio_response(account_id: str) -> GetOrdersResponse:
    return GetOrdersResponse(orders=[])


@pytest.fixture(scope="session")
def test_config(lot: int) -> IntervalStrategyConfig:
    return IntervalStrategyConfig(
        interval_size=0.8,
        days_back_to_consider=3,
        check_interval=600,
        stop_loss_percent=0.01,
        quantity_limit=lot,
    )


@pytest.fixture
def client() -> Client:
    with Client(settings.token) as client:
        yield client


class CandleHandler:
    def __init__(self, config: IntervalStrategyConfig):
        self.now = now()
        self.from_date = self.now - timedelta(days=15)
        self.candles = []
        self.config = config

    async def get_all_candles(self, **kwargs):
        logger.debug(f"get_all_candles called with figi={kwargs.get('figi')}, interval={kwargs.get('interval')}")
        if not self.candles:
            logger.info("Candles not cached, fetching from API...")
            with Client(settings.token) as client:
                # Получаем свечи напрямую без кэша
                self.candles = list(
                    client.get_all_candles(
                        figi=kwargs["figi"],
                        to=self.now,
                        from_=self.from_date,
                        interval=kwargs["interval"],
                    )
                )
            logger.info(f"Fetched {len(self.candles)} candles")

        any_returned = False
        for candle in self.candles:
            if self.from_date < candle.time:
                if candle.time < self.from_date + timedelta(days=self.config.days_back_to_consider):
                    any_returned = True
                    yield candle
                else:
                    break

        if not any_returned:
            logger.warning("No candles returned, raising NoMoreDataError")
            raise NoMoreDataError()
        self.from_date += timedelta(seconds=self.config.check_interval)

    async def get_last_prices(self, figi: List[str]) -> GetLastPricesResponse:
        logger.debug(f"get_last_prices called with figi={figi}")
        for candle in self.candles:
            if candle.time >= self.from_date + timedelta(days=self.config.days_back_to_consider):
                logger.info(f"Returning last price for {figi[0]}: {candle.close}")
                return GetLastPricesResponse(
                    last_prices=[LastPrice(figi=figi[0], price=candle.close, time=candle.time)]
                )
        logger.warning("No candles found for get_last_prices, raising NoMoreDataError")
        raise NoMoreDataError()


class PortfolioHandler:
    def __init__(self, figi: str, comission: float, lot: int, candle_handler: CandleHandler):
        self.positions = 0
        self.resources = 0
        self.figi = figi
        self.lot = lot
        self.comission = comission
        self.candle_handler = candle_handler
        self.average_price = MoneyValue(units=0, nano=0)

    async def get_portfolio(self, **kwargs) -> PortfolioResponse:
        return PortfolioResponse(
            positions=[
                PortfolioPosition(
                    figi=self.figi,
                    quantity=Quotation(units=self.positions, nano=0),
                    average_position_price=self.average_price,
                )
            ]
        )

    async def post_order(
        self, quantity: int = 0, direction: OrderDirection = OrderDirection(0), **kwargs
    ):
        logger.info(f"post_order called: quantity={quantity}, direction={direction}")
        last_price_quotation = (
            (await self.candle_handler.get_last_prices(figi=[self.figi])).last_prices[0].price
        )
        last_price = quotation_to_float(last_price_quotation)
        items_quantity = quantity * self.lot
        # TODO: Make it count average price respecting amount
        if direction == OrderDirection.ORDER_DIRECTION_BUY:
            logger.info(f"BUY order: adding {items_quantity} positions, cost={quantity * last_price}")
            self.positions += items_quantity
            self.resources -= quantity * last_price + (self.comission * quantity * last_price)
            self.average_price = MoneyValue(
                units=last_price_quotation.units, nano=last_price_quotation.nano
            )
        elif direction == OrderDirection.ORDER_DIRECTION_SELL:
            logger.info(f"SELL order: removing {items_quantity} positions, gain={quantity * last_price}")
            self.positions -= items_quantity
            self.resources += quantity * last_price - (self.comission * quantity * last_price)
            self.average_price = MoneyValue(units=0, nano=0)

        return PostOrderResponse(order_id=uuid.uuid4().hex)


@pytest.fixture(scope="session")
def candle_handler(test_config: IntervalStrategyConfig) -> CandleHandler:
    logger.info("Creating CandleHandler fixture")
    return CandleHandler(test_config)


@pytest.fixture(scope="session")
def portfolio_handler(
    figi: str, comission: float, lot: int, candle_handler: CandleHandler
) -> PortfolioHandler:
    logger.info(f"Creating PortfolioHandler fixture for figi={figi}")
    return PortfolioHandler(figi, comission, lot, candle_handler)


@pytest.fixture
def mock_client(
    mocker: MockerFixture,
    instrument_response: InstrumentResponse,
    accounts_response: GetAccountsResponse,
    orders_response: GetOrdersResponse,
    candle_handler: CandleHandler,
    portfolio_handler: PortfolioHandler,
    figi: str,
) -> TinkoffClient:
    logger.info("Setting up mock_client fixture")
    client_mock = mocker.patch("app.strategies.interval.IntervalStrategy.client")
    client_mock.get_instrument = AsyncMock(return_value=instrument_response)
    client_mock.get_accounts = AsyncMock(return_value=accounts_response)
    client_mock.get_orders = AsyncMock(return_value=orders_response)

    client_mock.get_all_candles = candle_handler.get_all_candles
    client_mock.get_last_prices = AsyncMock(side_effect=candle_handler.get_last_prices)

    client_mock.get_portfolio = AsyncMock(side_effect=portfolio_handler.get_portfolio)
    client_mock.post_order = AsyncMock(side_effect=portfolio_handler.post_order)

    logger.info("mock_client fixture setup complete")
    return client_mock
