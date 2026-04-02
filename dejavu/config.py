import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Setup base configuration
    APP_NAME: str = "DejaVu v2"
    DATA_DIR: str = os.path.expanduser("~/.dejavu/data")
    LOG_LEVEL: str = "INFO"
    
    # Data Provider configuration
    DEFAULT_PROVIDER: str = "alpaca"
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()

import logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
