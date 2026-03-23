from datetime import date

from app.sqlite.client import SQLiteClient


class StopLossSQLiteClient:
    """SQLite client for persisting stop loss triggers across restarts."""

    def __init__(self, db_name: str = "stats.db"):
        self.db_client = SQLiteClient(db_name)
        self.db_client.connect()
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the stop_loss_triggers table if it doesn't exist."""
        self.db_client.execute(
            """
            CREATE TABLE IF NOT EXISTS stop_loss_triggers (
                figi TEXT NOT NULL,
                trigger_date DATE NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (figi, trigger_date)
            )
            """
        )

    def add_trigger(self, figi: str, trigger_date: date = None) -> None:
        """
        Add a stop loss trigger for a specific figi and date.
        
        :param figi: The instrument FIGI
        :param trigger_date: The date of the trigger (defaults to today)
        """
        if trigger_date is None:
            trigger_date = date.today()
        self.db_client.execute_insert(
            "INSERT INTO stop_loss_triggers (figi, trigger_date) VALUES (?, ?)",
            (figi, trigger_date.isoformat()),
        )

    def get_triggers_for_date(self, trigger_date: date = None) -> list[str]:
        """
        Get all figis that had stop loss triggered on a specific date.
        
        :param trigger_date: The date to check (defaults to today)
        :return: List of FIGIs with stop loss triggers
        """
        if trigger_date is None:
            trigger_date = date.today()
        rows = self.db_client.execute_select(
            "SELECT figi FROM stop_loss_triggers WHERE trigger_date = ?",
            (trigger_date.isoformat(),),
        )
        return [row[0] for row in rows]

    def clear_triggers_for_date(self, trigger_date: date = None) -> None:
        """
        Clear all stop loss triggers for a specific date.
        
        :param trigger_date: The date to clear (defaults to today)
        """
        if trigger_date is None:
            trigger_date = date.today()
        self.db_client.execute_delete(
            "DELETE FROM stop_loss_triggers WHERE trigger_date = ?",
            (trigger_date.isoformat(),),
        )

    def close(self) -> None:
        """Close the database connection."""
        self.db_client.close()
