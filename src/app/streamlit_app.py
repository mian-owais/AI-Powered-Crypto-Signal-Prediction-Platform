"""
streamlit_app.py - Real-time multi-coin trading dashboard with RL integration.
Run with: streamlit run src/app/streamlit_app.py
"""

import streamlit as st
import requests
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import io
import base64
from src.eval_utils import (
    compute_classification_metrics,
    plot_confusion_matrix,
    plot_roc_curve,
    plot_calibration_curve,
    plot_rolling_metrics,
    plot_backtest_performance,
    get_worst_predictions,
    load_prediction_logs,
    load_backtest_results,
)
from src.model_manager import predict_with_model, train_model_for_prediction
from src.self_learning_loop import verify_pending_predictions
from src.rl_agent import DQNAgent
from src.model_predict_trend import predict_and_log
import sys
import os

# Fix import path for Streamlit Cloud deployment
ROOT_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# Optional dependencies
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:
    canvas = None

# App constants
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINS = {
    "Bitcoin": "bitcoin",
    "Ethereum": "ethereum",
    "Dogecoin": "dogecoin",
    "Solana": "solana",
    "Cardano": "cardano",
}
DEFAULT_REFRESH_SECONDS = 60

# Import helper modules from package


def _generate_mock_data(days: float = 1.0) -> pd.DataFrame:
    """Generate simple mock price+volume series used as fallback when API fails."""
    points = int(max(60, min(1440, days * 24 * 60)))
    now = datetime.utcnow()
    timestamps = [now - timedelta(minutes=5 * i) for i in range(points)][::-1]
    base_price = 35000
    trend = np.linspace(0, 0.02 * base_price, points)
    noise = np.random.normal(0, base_price * 0.01, points)
    prices = base_price + trend + noise
    base_volume = 1000000
    volume_noise = np.random.normal(0, base_volume * 0.2, points)
    volumes = np.maximum(base_volume + volume_noise, 0)
    df = pd.DataFrame({"ts": pd.to_datetime(timestamps),
                      "price": prices, "volume": volumes})
    return df.set_index("ts")


def fetch_market_chart(coin_id: str, days: float = 1.0) -> pd.DataFrame:
    """Fetch market_chart from CoinGecko with retries and fallback to mock data."""
    import time
    max_retries = 3
    retry_delay = 15
    for attempt in range(max_retries):
        try:
            url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
            params = {"vs_currency": "usd", "days": str(days)}

            # Add API key if available
            import os
            api_key = os.environ.get("COINGECKO_API_KEY")
            if api_key:
                params["x_cg_demo_api_key"] = api_key

            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 429:
                if attempt < max_retries - 1:
                    st.warning("CoinGecko rate limit hit, retrying...")
                    time.sleep(retry_delay)
                    continue
                else:
                    st.warning("Using mock data due to API rate limits")
                    return _generate_mock_data(days)
            r.raise_for_status()
            data = r.json()
            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])
            if not prices:
                raise ValueError("Empty price series from CoinGecko")
            dfp = pd.DataFrame(prices, columns=["ts", "price"]).assign(
                ts=lambda d: pd.to_datetime(d["ts"], unit="ms"))
            dfv = pd.DataFrame(volumes, columns=["ts", "volume"]).assign(
                ts=lambda d: pd.to_datetime(d["ts"], unit="ms"))
            df = pd.merge_asof(dfp.sort_values(
                "ts"), dfv.sort_values("ts"), on="ts")
            df = df.set_index("ts")
            df["price"] = df["price"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                return _generate_mock_data(days)


def build_ohlcv(df_prices: pd.DataFrame, rule: str = "1T") -> pd.DataFrame:
    """Aggregate price series into OHLCV."""
    o = df_prices["price"].resample(rule).ohlc()
    v = df_prices["volume"].resample(rule).sum()
    df = o.join(v).dropna()
    df.columns = ["open", "high", "low", "close", "volume"]
    return df


def predict_trend(df_ohlc: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
    """Simple rule-based predictor."""
    if df_ohlc.empty:
        return {"trend": "Unknown", "pct": 0.0, "color": "gray", "emoji": "❓"}
    window = max(3, min(20, int(len(df_ohlc) * 0.2)))
    recent = df_ohlc["close"].iloc[-window:]
    latest = df_ohlc["close"].iloc[-1]
    avg = recent.mean()
    pct = (latest - avg) / (avg + 1e-9)
    thresh = 0.003
    if pct > thresh:
        return {"trend": "Increase", "pct": float(pct), "color": "green", "emoji": "📈"}
    elif pct < -thresh:
        return {"trend": "Decrease", "pct": float(pct), "color": "red", "emoji": "📉"}
    else:
        return {"trend": "Constant", "pct": float(pct), "color": "goldenrod", "emoji": "⚖️"}


def plot_candlestick(df_ohlc: pd.DataFrame, title: str = "Price") -> go.Figure:
    """Create candlestick chart with volume."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.7, 0.3])
    fig.add_trace(
        go.Candlestick(x=df_ohlc.index, open=df_ohlc["open"], high=df_ohlc["high"],
                       low=df_ohlc["low"], close=df_ohlc["close"], name="OHLC"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df_ohlc.index, y=df_ohlc["close"].rolling(
            window=20).mean(), line=dict(color="#B2DFDB", width=1), name="MA20"),
        row=1, col=1,
    )
    colors = ["#26A69A" if c >= o else "#EF5350" for o,
              c in zip(df_ohlc["open"], df_ohlc["close"])]
    fig.add_trace(go.Bar(
        x=df_ohlc.index, y=df_ohlc["volume"], marker_color=colors, opacity=0.5, name="Volume"), row=2, col=1)
    fig.update_layout(template="plotly_dark", title=title,
                      xaxis_rangeslider_visible=False, hovermode="x unified")
    return fig


def format_price(p: float) -> str:
    """Format price for display."""
    return f"${p:,.2f}" if p >= 1 else f"${p:.8f}"


def create_evaluation_report(df_pred: pd.DataFrame, df_backtest: pd.DataFrame, metrics: Dict, coin: str, timeframe: str, model: str) -> bytes:
    """Create a minimal PDF evaluation report."""
    if canvas is None:
        return b""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50,
                 f"Model Evaluation Report: {model} on {coin} ({timeframe})")
    c.setFont("Helvetica", 10)
    y = height - 100
    for name, value in metrics.items():
        y -= 15
        c.drawString(50, y, f"{name}: {value:.4f}")
    c.drawString(
        50, 30, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def render_trading_tab():
    """Render the live trading dashboard tab."""
    st.title("📈 Real-time Multi-Coin Candlestick + Prediction Dashboard")
    with st.sidebar:
        st.header("Settings")

        # Get current index for selectboxes based on session state
        coin_options = list(COINS.keys())
        coin_index = coin_options.index(
            st.session_state.selected_coin) if st.session_state.selected_coin in coin_options else 0

        timeframe_options = ["Next 5 Minutes", "Next Day", "Next Week"]
        timeframe_index = timeframe_options.index(
            st.session_state.selected_timeframe) if st.session_state.selected_timeframe in timeframe_options else 1

        model_options = ["RandomForest", "XGBoost", "RL_Agent", "Random"]
        model_index = model_options.index(
            st.session_state.selected_model) if st.session_state.selected_model in model_options else 0

        # Create selectboxes that sync with session state
        # When user changes these, update the shared session state
        coin_label = st.selectbox(
            "Cryptocurrency", coin_options, index=coin_index, key="trading_coin")
        timeframe = st.selectbox("Prediction timeframe", timeframe_options,
                                 index=timeframe_index, key="trading_timeframe")
        model_name = st.selectbox(
            "Prediction Model", model_options, index=model_index, key="trading_model")

        # Sync widget values to shared session state
        st.session_state.selected_coin = coin_label
        st.session_state.selected_timeframe = timeframe
        st.session_state.selected_model = model_name
        auto_refresh = st.checkbox("Auto Refresh (60s)", value=True)
        retrain_model = st.checkbox(
            "Retrain Model with Fresh Data", value=True)
        st.markdown("---")
        st.markdown("Data source: CoinGecko API")
        st.markdown(
            "**Note:** Models train on fresh + historical data when you change settings")

    coin_id = COINS[coin_label]
    if auto_refresh and st_autorefresh is not None:
        st_autorefresh(interval=DEFAULT_REFRESH_SECONDS *
                       1000, key="autorefresh")

    try:
        if timeframe == "Next 5 Minutes":
            df_raw = fetch_market_chart(coin_id, days=0.1)
            ohlc = build_ohlcv(df_raw, rule="1T").iloc[-120:]
            chart_title = f"{coin_label} — 1-minute candles"
            training_days = 0.1
        elif timeframe == "Next Day":
            df_raw = fetch_market_chart(coin_id, days=2)
            ohlc = build_ohlcv(df_raw, rule="30T").iloc[-48:]
            chart_title = f"{coin_label} — 30-minute candles"
            training_days = 2.0
        else:
            df_raw = fetch_market_chart(coin_id, days=14)
            ohlc = build_ohlcv(df_raw, rule="6H").iloc[-56:]
            chart_title = f"{coin_label} — 6-hour candles"
            training_days = 14.0
    except Exception as e:
        st.error(f"Failed to fetch market data: {e}")
        return

    latest_price = float(ohlc["close"].iloc[-1])

    # Use ML model prediction if not "Random"
    if model_name != "Random":
        try:
            with st.spinner(f"Training {model_name} and making prediction with fresh data..."):
                ml_pred = predict_with_model(
                    coin_id=coin_id,
                    model_name=model_name,
                    timeframe=timeframe,
                    days=training_days,
                    retrain=retrain_model
                )

                # Map ML prediction to display format
                pred_label = ml_pred.get('predicted_label', 'Unknown')
                pred_pct = ml_pred.get('predicted_pct_change', 0.0)
                confidence = ml_pred.get('confidence', 0.0)

                if pred_label == "Increase":
                    pred = {"trend": "Increase", "pct": float(
                        pred_pct), "color": "green", "emoji": "📈"}
                elif pred_label == "Decrease":
                    pred = {"trend": "Decrease", "pct": float(
                        pred_pct), "color": "red", "emoji": "📉"}
                else:
                    pred = {"trend": "Constant", "pct": float(
                        pred_pct), "color": "goldenrod", "emoji": "⚖️"}

                pred['confidence'] = confidence
                pred['model_used'] = model_name
                pred['predicted_price'] = ml_pred.get(
                    'predicted_price', latest_price)
        except Exception as e:
            st.warning(
                f"ML model prediction failed ({e}), using fallback prediction")
            pred = predict_trend(ohlc, timeframe)
            pred['model_used'] = "Fallback"
    else:
        # Use simple rule-based prediction
        pred = predict_trend(ohlc, timeframe)
        pred['model_used'] = "Random"

    k1, k2, k3, k4 = st.columns([2, 2, 2, 2])
    with k1:
        st.markdown("**Current Price**")
        st.metric(label="", value=format_price(latest_price))
    with k2:
        st.markdown("**Prediction**")
        st.markdown(f"<div style='background-color:{pred['color']};padding:12px;border-radius:6px;text-align:center'><strong style='font-size:20px;color:#000'>{pred['emoji']} {pred['trend']}</strong><div style='font-size:12px;color:#111'>Change: {pred['pct']*100:+.2f}%</div></div>", unsafe_allow_html=True)
    with k3:
        st.markdown("**Model**")
        st.write(pred.get('model_used', model_name))
        if 'confidence' in pred:
            st.write(f"Confidence: {pred['confidence']:.1f}%")
    with k4:
        st.markdown("**Auto-refresh**")
        st.write("On" if auto_refresh else "Off")
        if 'predicted_price' in pred:
            st.write(f"Predicted: {format_price(pred['predicted_price'])}")

    st.markdown("---")
    col_chart, col_info = st.columns([4, 1])
    with col_chart:
        fig = plot_candlestick(ohlc, title=chart_title)
        st.plotly_chart(fig, use_container_width=True)
    with col_info:
        st.markdown("**Details**")
        st.write(f"Latest: {format_price(latest_price)}")
        st.write(f"Data points: {len(ohlc)}")
        st.write(f"Model: {pred.get('model_used', model_name)}")
        if retrain_model:
            st.write("✓ Retrained with fresh data")


def render_evaluation_tab():
    """Render the evaluation and error analysis tab."""
    st.title("📊 Evaluation & Error Analysis")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

    # Get current index for selectboxes based on session state
    coin_options = list(COINS.keys())
    coin_index = coin_options.index(
        st.session_state.selected_coin) if st.session_state.selected_coin in coin_options else 0

    timeframe_options = ["Next 5 Minutes", "Next Day", "Next Week"]
    timeframe_index = timeframe_options.index(
        st.session_state.selected_timeframe) if st.session_state.selected_timeframe in timeframe_options else 1

    model_options = ["RandomForest", "XGBoost", "LSTM", "RL_Agent"]
    model_index = model_options.index(
        st.session_state.selected_model) if st.session_state.selected_model in model_options else 0

    with col1:
        coin_label = st.selectbox(
            "Cryptocurrency", coin_options, index=coin_index, key="eval_coin")
        coin_id = COINS[coin_label]
        # Sync widget value to shared session state
        st.session_state.selected_coin = coin_label
    with col2:
        timeframe = st.selectbox(
            "Timeframe", timeframe_options, index=timeframe_index, key="eval_timeframe")
        # Sync widget value to shared session state
        st.session_state.selected_timeframe = timeframe
    with col3:
        model = st.selectbox(
            "Model", model_options, index=model_index, key="eval_model")
        # Sync widget value to shared session state
        st.session_state.selected_model = model
    with col4:
        date_range = st.date_input("Analysis Period", value=(
            datetime.now() - timedelta(days=90), datetime.now()), key="eval_dates")

    start_date, end_date = date_range
    df_pred = load_prediction_logs(
        coin_id, timeframe, model, start_date, end_date)
    df_backtest = load_backtest_results(coin_id, timeframe, model)

    st.markdown("### 📈 Performance Overview")
    metrics = compute_classification_metrics(df_pred)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Accuracy", f"{metrics.get('accuracy', 0):.2%}")
    with m2:
        st.metric("Precision", f"{metrics.get('weighted_precision', 0):.2%}")
    with m3:
        st.metric("Recall", f"{metrics.get('weighted_recall', 0):.2%}")
    with m4:
        st.metric("F1 Score", f"{metrics.get('weighted_f1', 0):.2%}")

    st.markdown("### 📊 Classification Diagnostics")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(plot_confusion_matrix(
            df_pred), use_container_width=True)
    with c2:
        st.plotly_chart(plot_roc_curve(df_pred), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(plot_calibration_curve(
            df_pred), use_container_width=True)
    with c2:
        window = st.slider("Rolling Window (days)",
                           min_value=3, max_value=30, value=7)
        st.plotly_chart(plot_rolling_metrics(
            df_pred, window), use_container_width=True)

    st.markdown("### 💰 Trading Performance")
    st.plotly_chart(plot_backtest_performance(
        df_backtest), use_container_width=True)

    st.markdown("### ❌ Error Analysis")
    c1, c2 = st.columns(2)
    with c1:
        n_worst = st.slider("Number of predictions", min_value=5,
                            max_value=20, value=10, key="worst_conf")
        worst_conf = get_worst_predictions(df_pred, n=n_worst, by="confidence")
        st.dataframe(worst_conf)
    with c2:
        n_worst_e = st.slider("Number of predictions (errors)",
                              min_value=5, max_value=20, value=10, key="worst_error")
        worst_error = get_worst_predictions(df_pred, n=n_worst_e, by="error")
        st.dataframe(worst_error)

    st.markdown("### 🤖 Self-Learning & RL Agent")
    col_a, col_b = st.columns([2, 1])
    verification_log = Path("data/logs/verification_log.csv")
    prediction_log = Path("data/logs/prediction_log.csv")

    with col_a:
        st.subheader("Learning Progress")
        if verification_log.exists():
            df_ver = pd.read_csv(verification_log)
            df_ver["verified_at"] = pd.to_datetime(df_ver["verified_at"])
            df_ver = df_ver.sort_values("verified_at")
            df_ver["cum_reward"] = df_ver["reward"].cumsum()
            st.line_chart(df_ver.set_index("verified_at")["cum_reward"])
            df_ver["correct"] = (df_ver["reward"] > 0).astype(int)
            rolling = df_ver["correct"].rolling(20, min_periods=1).mean()
            st.line_chart(pd.DataFrame(
                {"rolling_accuracy": rolling.values}, index=df_ver["verified_at"]))
            st.markdown("#### Recent Verifications")
            st.dataframe(df_ver.sort_values(
                "verified_at", ascending=False).head(50))
        else:
            st.write(
                "No verification data yet. Run predictions and wait for verification or click 'Verify Now'.")

    with col_b:
        st.subheader("Agent Controls")
        if st.button("Verify Now"):
            agent = DQNAgent(state_size=4)
            processed = verify_pending_predictions(agent)
            st.success(
                f"Processed {processed} pending predictions and updated agent buffer.")
        if st.button("Re-learn Now"):
            agent = DQNAgent(state_size=4)
            verification_path = "data/logs/verification_log.csv"
            feature_keys = ["rsi", "ema_diff", "momentum", "volatility"]
            if hasattr(agent, "train_from_logs"):
                agent.train_from_logs(verification_path, feature_keys)
                st.success(
                    "Offline re-training completed (if torch is available).")
            else:
                st.info("Agent training skipped (torch not available).")
        if st.button("Make Prediction Now"):
            agent = DQNAgent(state_size=4)
            pred = predict_and_log(agent, coin_id, timeframe)
            st.write("Logged prediction:")
            st.json(pred)


def main():
    """Main application entry point."""
    st.set_page_config(page_title="Crypto Trading Dashboard",
                       layout="wide", initial_sidebar_state="expanded")

    # Initialize session state for synchronized selections
    if 'selected_coin' not in st.session_state:
        st.session_state.selected_coin = list(COINS.keys())[0]
    if 'selected_timeframe' not in st.session_state:
        st.session_state.selected_timeframe = "Next Day"
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = "RandomForest"

    tab1, tab2 = st.tabs(["🎯 Live Trading", "📊 Evaluation"])
    with tab1:
        render_trading_tab()
    with tab2:
        render_evaluation_tab()


if __name__ == "__main__":
    main()
