import asyncio
from datetime import datetime

from tinkoff.invest import OrderExecutionReportStatus, AioRequestError
from tinkoff.invest.grpc.instruments_pb2 import INSTRUMENT_ID_TYPE_FIGI

from app.client import TinkoffClient
from app.stats.sqlite_client import StatsSQLiteClient
from app.strategies.models import StrategyName
from app.utils.quotation import quotation_to_float


async def get_instrument_name(client: TinkoffClient, figi: str) -> str:
    """Get instrument name by FIGI."""
    try:
        response = await client.get_instrument(id_type=INSTRUMENT_ID_TYPE_FIGI, id=figi)
        return response.instrument.name or ""
    except AioRequestError:
        return ""


FINAL_ORDER_STATUSES = [
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_CANCELLED,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
]


class StatsHandler:
    def __init__(self, strategy: StrategyName, broker_client: TinkoffClient):
        self.strategy = strategy
        self.db = StatsSQLiteClient(db_name="stats.db")
        self.broker_client = broker_client

    async def handle_new_order(self, account_id: str, order_id: str) -> None:
        """
        This method is called when new order is created.
        It waits for the order to be filled, canceled, or rejected
        and logs its information to the database

        To prevent affecting the strategy execution,
        this method can be called with asyncio.create_task()

        :param account_id: id of the account the order was created for
        :param order_id: id of the order to track its status
        :return: None
        """
        try:
            order_state = await self.broker_client.get_order_state(
                account_id=account_id, order_id=order_id
            )
        except AioRequestError:
            return
        instrument_name = await get_instrument_name(self.broker_client, order_state.figi)
        average_position_price = quotation_to_float(order_state.average_position_price) if hasattr(order_state, 'average_position_price') and order_state.average_position_price else None
        executed_commission = quotation_to_float(order_state.executed_commission) if hasattr(order_state, 'executed_commission') and order_state.executed_commission else None
        initial_commission = quotation_to_float(order_state.initial_commission) if hasattr(order_state, 'initial_commission') and order_state.initial_commission else None
        executed_order_price = quotation_to_float(order_state.executed_order_price) if hasattr(order_state, 'executed_order_price') and order_state.executed_order_price else None
        total_order_amount = quotation_to_float(order_state.total_order_amount) if hasattr(order_state, 'total_order_amount') and order_state.total_order_amount else None
        self.db.add_order(
            order_id=order_id,
            figi=order_state.figi,
            order_direction=str(order_state.direction),
            price=quotation_to_float(order_state.total_order_amount),
            quantity=order_state.lots_requested,
            status=str(order_state.execution_report_status),
            order_datetime=order_state.order_date,
            instrument_name=instrument_name,
            average_position_price=average_position_price,
            executed_commission=executed_commission,
            initial_commission=initial_commission,
            executed_order_price=executed_order_price,
            total_order_amount=total_order_amount,
        )
        while order_state.execution_report_status not in FINAL_ORDER_STATUSES:
            await asyncio.sleep(10)
            order_state = await self.broker_client.get_order_state(
                account_id=account_id, order_id=order_id
            )
        self.db.update_order_status(
            order_id=order_id, status=str(order_state.execution_report_status)
        )
