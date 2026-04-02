from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional

class DataProvider(ABC):
    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "1m",
        extended_hours: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical bars for a given symbol.
        Must return a pandas DataFrame with DatetimeIndex and OHLCV columns.
        """
        pass
