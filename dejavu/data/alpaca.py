import pandas as pd
from typing import Optional
import logging
import requests
from io import StringIO

from dejavu.data.provider import DataProvider
from dejavu.config import settings

logger = logging.getLogger(__name__)

class AlpacaProvider(DataProvider):
    def __init__(self, api_key: str = "", secret_key: str = ""):
        self.api_key = api_key or settings.ALPACA_API_KEY
        self.secret_key = secret_key or settings.ALPACA_SECRET_KEY
        logger.debug("Initialized AlpacaProvider")
        
    def fetch_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "5Min",
        extended_hours: bool = True
    ) -> pd.DataFrame:
        logger.info(f"Fetching {symbol} from Alpaca: {start_date} to {end_date} ({timeframe})")
        if not self.api_key or not self.secret_key or self.api_key == "your_api_key_here":
            raise ValueError("Alpaca API keys missing or invalid.")
        
        # Mapping timeframe e.g. "5m" -> "5Min" for Alpaca
        tf_mapped = timeframe.replace("m", "Min") if "m" in timeframe else timeframe
        
        url = "https://data.alpaca.markets/v2/stocks/bars"
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "accept": "application/json"
        }
        
        # We need RFC3339 for start and end
        start_rfc = pd.to_datetime(start_date).strftime("%Y-%m-%dT00:00:00Z")
        end_rfc = pd.to_datetime(end_date).strftime("%Y-%m-%dT23:59:59Z")
        
        params = {
            "symbols": symbol,
            "timeframe": tf_mapped,
            "start": start_rfc,
            "end": end_rfc,
            "limit": 10000,
            "feed": "iex" # explicit IEX requirement
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if "bars" not in data or symbol not in data["bars"]:
            raise ValueError(f"No bars returned for {symbol} from Alpaca IEX")
            
        bars = data["bars"][symbol]
        df = pd.DataFrame(bars)
        
        # Alpaca gives: t (timestamp), o, h, l, c, v
        df = df.rename(columns={
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        })
        
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        
        required = ['open', 'high', 'low', 'close', 'volume']
        df = df[required]
        df['session_type'] = 'regular' # simplified tagging for MVP
        
        return df
