import pandas as pd
from typing import Optional
import logging
from dejavu.data.provider import DataProvider

logger = logging.getLogger(__name__)

class YahooProvider(DataProvider):
    def __init__(self):
        logger.debug("Initialized YahooProvider fallback")
        
    def fetch_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "5m",
        extended_hours: bool = True
    ) -> pd.DataFrame:
        logger.info(f"Fetching {symbol} from YahooQuery: {start_date} to {end_date} ({timeframe})")
        from yahooquery import Ticker
        
        t = Ticker(symbol)
        df = t.history(start=start_date, end=end_date, interval=timeframe)
        
        if df is None or (isinstance(df, dict) and symbol in df and isinstance(df[symbol], str)):
            # Ticker fetch error returns a dict with string error usually
            raise ValueError(f"No data returned from YahooQuery for {symbol}")
            
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError(f"No data returned from YahooQuery for {symbol}")
            
        df = df.reset_index()
        if 'date' in df.columns:
            df = df.set_index('date')
        
        # Ensure index is Datetime
        df.index = pd.to_datetime(df.index)
        
        # Rename columns to match schema
        cols = {c: c.lower() for c in df.columns}
        df = df.rename(columns=cols)
        
        # Ensure we have ohlcv
        required = ['open', 'high', 'low', 'close', 'volume']
        for r in required:
            if r not in df.columns:
                df[r] = df['close'] if r != 'volume' else 0
                
        df = df[required]
        df['session_type'] = 'regular' # simplified since Yahoo gives mixed signals on session tagging without strict parsing
        return df
