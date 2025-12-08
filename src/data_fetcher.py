"""data_fetcher.py
Minimal data fetcher and feature extractor.
Provides caching and simple technical indicators used as RL state.
"""
from pathlib import Path
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def fetch_price_series(coin_id: str, days: float = 7.0, interval: str = '5m') -> pd.DataFrame:
    """Fetch price series (ts, price) for the last `days` days. Falls back to empty DataFrame on failure."""
    try:
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": str(days)}
        
        # Add API key if available
        import os
        api_key = os.environ.get("COINGECKO_API_KEY")
        if api_key:
            params["x_cg_demo_api_key"] = api_key
            
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        prices = data.get('prices', [])
        df = pd.DataFrame(prices, columns=['ts', 'price']).assign(
            ts=lambda d: pd.to_datetime(d['ts'], unit='ms')).set_index('ts')
        return df
    except Exception:
        return pd.DataFrame()


def simple_features_from_series(df: pd.DataFrame) -> dict:
    """Compute a small set of features from a price series: returns RSI, EMA diff, volatility, momentum, volume omitted."""
    out = {
        'rsi': 0.0,
        'ema_diff': 0.0,
        'volatility': 0.0,
        'momentum': 0.0
    }
    if df.empty:
        return out

    prices = df['price'].astype(float)
    # EMA difference (short - long)
    ema_short = prices.ewm(span=12, adjust=False).mean().iloc[-1]
    ema_long = prices.ewm(span=26, adjust=False).mean().iloc[-1]
    out['ema_diff'] = float((ema_short - ema_long) / max(1e-8, ema_long))

    # momentum: pct change over last N
    out['momentum'] = float(
        prices.pct_change().fillna(0).rolling(5).mean().iloc[-1])

    # volatility: rolling std of returns
    out['volatility'] = float(
        prices.pct_change().fillna(0).rolling(12).std().iloc[-1])

    # simple RSI approximation
    delta = prices.diff().dropna()
    up = delta.copy()
    down = delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    roll_up = up.rolling(14).mean().iloc[-1] if len(up) >= 14 else up.mean()
    roll_down = - \
        down.rolling(14).mean().iloc[-1] if len(down) >= 14 else -down.mean()
    rs = (roll_up / (roll_down + 1e-8)) if roll_down != 0 else 0.0
    out['rsi'] = float(100 - (100 / (1 + rs))) if roll_down != 0 else 50.0

    return out


def fetch_latest_price(coin_id: str) -> float:
    df = fetch_price_series(coin_id, days=0.3)
    if df.empty:
        return float('nan')
    return float(df['price'].iloc[-1])
