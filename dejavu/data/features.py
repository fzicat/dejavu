import pandas as pd
import logging

logger = logging.getLogger(__name__)

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes custom indicators: VWAP, PDH, PDL, PMH, PML, RelVol.
    Modifies DataFrame in-place and returns it.
    """
    logger.debug("Computing indicators: vwap, pdh, pdl, pmh, pml, rel_vol")
    
    if df.empty:
        return df
        
    # Typical price for VWAP
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    
    # Calculate daily cumulative volume and cumulative (vol * price)
    # Using the date component of the index to reset VWAP each day
    df['typ_x_vol'] = df['typical_price'] * df['volume']
    
    daily_groups = df.groupby(df.index.date)
    
    df['cum_vol'] = daily_groups['volume'].cumsum()
    df['cum_pv'] = daily_groups['typ_x_vol'].cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    
    # Clean up temporary columns
    df.drop(columns=['typical_price', 'typ_x_vol', 'cum_vol', 'cum_pv'], inplace=True)
    
    # Calculate Previous Day High/Low
    daily_high = daily_groups['high'].max().shift(1)
    daily_low = daily_groups['low'].min().shift(1)
    
    # Map back to rows by date
    dates_series = pd.Series(df.index.date, index=df.index)
    df['pdh'] = dates_series.map(daily_high)
    df['pdl'] = dates_series.map(daily_low)
    
    # Placeholder for Pre-Market High/Low (needs session_type mapping ideally)
    df['pmh'] = df['pdh'] 
    df['pml'] = df['pdl']
    
    # RelVol (Volume relative to rolling 20-period mean)
    rolling_vol_mean = df['volume'].rolling(window=20).mean()
    df['rel_vol'] = df['volume'] / rolling_vol_mean.replace(0, 1) # Avoid div by zero
    
    # Previous close for triggers
    df['prev_close'] = df['close'].shift(1)
    
    return df
