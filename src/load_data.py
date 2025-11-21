"""load_data.py - data fetching & IO helpers"""
import pandas as pd
import yfinance as yf

def load_price_series(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Load OHLCV series using yfinance. Returns DataFrame with DatetimeIndex."""
    t = yf.Ticker(ticker)
    df = t.history(period=period)
    return df
