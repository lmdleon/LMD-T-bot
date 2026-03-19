import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    
    app_name: str = "LMD T-bot"
    token: str
    account_id: str | None = None
    sandbox: bool = True
    log_level: int = logging.DEBUG
    tinkoff_library_log_level: int = logging.INFO
    use_candle_history_cache: bool = True


settings = Settings()
