from datetime import datetime

from app.sqlite.client import SQLiteClient


class StatsSQLiteClient:
    def __init__(self, db_name: str):
        self.db_client = SQLiteClient(db_name)
        self.db_client.connect()

        self._create_tables()

    def _create_tables(self):
        self.db_client.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                figi TEXT,
                direction TEXT,
                price REAL,
                quantity INTEGER,
                status TEXT,
                order_datetime DATETIME,
                instrument_name TEXT,
                average_position_price REAL,
                executed_commission REAL,
                initial_commission REAL,
                executed_order_price REAL,
                total_order_amount REAL
            )
            """
        )

    def add_order(
        self,
        order_id: str,
        figi: str,
        order_direction: str,
        price: float,
        quantity: int,
        status: str,
        order_datetime: datetime = None,
        instrument_name: str = None,
        average_position_price: float = None,
        executed_commission: float = None,
        initial_commission: float = None,
        executed_order_price: float = None,
        total_order_amount: float = None,
    ):
        if order_datetime is None:
            order_datetime = datetime.now()
        self.db_client.execute_insert(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, figi, order_direction, price, quantity, status, order_datetime.isoformat(), instrument_name, average_position_price, executed_commission, initial_commission, executed_order_price, total_order_amount),
        )

    def get_orders(self):
        return self.db_client.execute_select("SELECT * FROM orders")

    def update_order_status(self, order_id: str, status: str):
        self.db_client.execute_update(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id),
        )
