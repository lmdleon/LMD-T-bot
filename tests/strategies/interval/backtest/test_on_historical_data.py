import pytest
import logging
from pytest_mock import MockFixture

from app.client import TinkoffClient
from app.strategies.interval.IntervalStrategy import IntervalStrategy
from app.strategies.interval.models import IntervalStrategyConfig
from app.utils.quotation import quotation_to_float
from tests.strategies.interval.backtest.conftest import NoMoreDataError, PortfolioHandler

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestOnHistoricalData:
    @pytest.mark.asyncio
    async def test_on_historical_data(
        self,
        mocker: MockFixture,
        mock_client: TinkoffClient,
        portfolio_handler: PortfolioHandler,
        figi: str,
        lot: int,
        test_config: IntervalStrategyConfig,
    ):
        logger.info("Starting test_on_historical_data")
        mocker.patch("app.strategies.interval.IntervalStrategy.asyncio.sleep")
        stats_handler_mock = mocker.patch(
            "app.strategies.interval.IntervalStrategy.StatsHandler.handle_new_order"
        )
        mocker.patch("app.strategies.interval.IntervalStrategy.IntervalStrategy.ensure_market_open")
        strategy_instance = IntervalStrategy(figi=figi, **test_config.dict())
        with pytest.raises(NoMoreDataError):
            await strategy_instance.start()
        positions = portfolio_handler.positions
        average_price = portfolio_handler.average_price
        resources = portfolio_handler.resources
        logger.info(f"Test completed. Positions: {positions}, Average price: {average_price}, Resources: {resources}")
        with open("./tests/strategies/interval/backtest/test_on_historical_data.txt", "w") as f:
            f.write(
                f"Positions in portfolio: {positions} ({positions/lot} lots)\n"
                f"It's average price:     {quotation_to_float(average_price)}\n"
                f"Balance left:           {resources}\n"
                f"Orders made:            {len(stats_handler_mock.mock_calls)}"
            )
        assert False
