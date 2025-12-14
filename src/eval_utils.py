"""
eval_utils.py
------------
Utilities for model evaluation, error analysis, and performance visualization.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from sklearn.metrics import (
    confusion_matrix, classification_report, roc_curve, auc,
    precision_recall_curve, mean_squared_error, mean_absolute_error
)
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
try:
    import shap
except ImportError:
    shap = None
import joblib
from pathlib import Path

# Constants
PREDICTION_LOG_PATH = Path("data/logs/prediction_log.csv")
BACKTEST_RESULTS_PATH = Path("data/logs/backtest_results")
MODELS_PATH = Path("models")


@st.cache_data
def load_prediction_logs(
    coin: str,
    timeframe: str,
    model: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """Load and filter prediction logs for analysis.

    Args:
        coin: Cryptocurrency symbol (e.g., 'BTC')
        timeframe: Prediction horizon ('5min', '1d', '1w')
        model: Model name
        start_date: Analysis start date
        end_date: Analysis end date

    Returns:
        DataFrame with filtered prediction logs
    """
    try:
        df = pd.read_csv(PREDICTION_LOG_PATH)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Apply filters
        mask = (
            (df['coin'] == coin) &
            (df['timeframe'] == timeframe) &
            (df['model_name'] == model) &
            (df['timestamp'] >= start_date) &
            (df['timestamp'] <= end_date)
        )
        return df[mask].copy()
    except FileNotFoundError:
        # Return mock data for testing
        return _generate_mock_predictions(coin, timeframe, model, start_date, end_date)


@st.cache_data
def load_backtest_results(
    coin: str,
    timeframe: str,
    model: str
) -> pd.DataFrame:
    """Load backtest results for a specific model configuration.

    Args:
        coin: Cryptocurrency symbol
        timeframe: Trading timeframe
        model: Model name

    Returns:
        DataFrame with backtest results
    """
    filename = f"{model}_{coin}_{timeframe}.csv"
    try:
        df = pd.read_csv(BACKTEST_RESULTS_PATH / filename)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except FileNotFoundError:
        return _generate_mock_backtest(coin, timeframe, model)


@st.cache_data
def compute_classification_metrics(df: pd.DataFrame) -> Dict:
    """Compute classification performance metrics.

    Args:
        df: DataFrame with columns: predicted_label, actual_label

    Returns:
        Dict with metrics (accuracy, precision, recall, f1)
    """
    if df.empty:
        return {'accuracy': 0.0, 'weighted_precision': 0.0, 'weighted_recall': 0.0, 'weighted_f1': 0.0}

    # Check if required columns exist
    if 'actual_label' not in df.columns or 'predicted_label' not in df.columns:
        return {'accuracy': 0.0, 'weighted_precision': 0.0, 'weighted_recall': 0.0, 'weighted_f1': 0.0}

    y_true = df['actual_label']
    y_pred = df['predicted_label']

    # Get classification report as dict
    report = classification_report(y_true, y_pred, output_dict=True)

    # Extract overall metrics
    metrics = {
        'accuracy': report['accuracy'],
        'weighted_precision': report['weighted avg']['precision'],
        'weighted_recall': report['weighted avg']['recall'],
        'weighted_f1': report['weighted avg']['f1-score']
    }

    # Add per-class metrics
    for label in ['Increase', 'Decrease', 'Constant']:
        if label in report:
            metrics[f'{label}_precision'] = report[label]['precision']
            metrics[f'{label}_recall'] = report[label]['recall']
            metrics[f'{label}_f1'] = report[label]['f1-score']

    return metrics


def plot_confusion_matrix(df: pd.DataFrame) -> go.Figure:
    """Plot confusion matrix heatmap using plotly.

    Args:
        df: DataFrame with actual and predicted labels

    Returns:
        Plotly figure object
    """
    # Check if required columns exist
    if df.empty or 'actual_label' not in df.columns or 'predicted_label' not in df.columns:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(text="No verified predictions available yet.<br>Predictions need to be verified to show confusion matrix.",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Compute confusion matrix
    cm = confusion_matrix(df['actual_label'], df['predicted_label'])
    labels = sorted(df['actual_label'].unique())

    # Create heatmap using text_auto (px.imshow doesn't accept `text` kwarg)
    fig = px.imshow(
        cm,
        x=labels,
        y=labels,
        labels=dict(x="Predicted", y="Actual", color="Count"),
        color_continuous_scale="RdYlBu_r",
        aspect='equal',
        text_auto=True,
    )

    fig.update_layout(
        title="Confusion Matrix",
        xaxis_title="Predicted Label",
        yaxis_title="Actual Label",
        width=600,
        height=500
    )

    return fig


def plot_roc_curve(df: pd.DataFrame) -> go.Figure:
    """Plot ROC curves for each class (one-vs-rest).

    Args:
        df: DataFrame with actual labels and predicted probabilities

    Returns:
        Plotly figure with ROC curves
    """
    # Check if required columns exist
    if df.empty or 'actual_label' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No verified predictions available yet.<br>Predictions need to be verified to show ROC curve.",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure()
    classes = sorted(df['actual_label'].unique())

    for label in classes:
        # Convert to binary problem
        y_true = (df['actual_label'] == label).astype(int)
        y_score = df[f'prob_{label}']

        # Compute ROC curve
        fpr, tpr, _ = roc_curve(y_true, y_score)
        roc_auc = auc(fpr, tpr)

        # Add trace
        fig.add_trace(
            go.Scatter(
                x=fpr,
                y=tpr,
                name=f'{label} (AUC = {roc_auc:.2f})',
                mode='lines'
            )
        )

    # Add diagonal line
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode='lines',
            line=dict(dash='dash', color='gray'),
            showlegend=False
        )
    )

    fig.update_layout(
        title="ROC Curves (One-vs-Rest)",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        width=700,
        height=500,
        showlegend=True
    )

    return fig


def plot_calibration_curve(df: pd.DataFrame) -> go.Figure:
    """Plot calibration (reliability) curve.

    Args:
        df: DataFrame with actual labels and predicted probabilities

    Returns:
        Plotly figure with calibration curves
    """
    # Check if required columns exist
    if df.empty or 'actual_label' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No verified predictions available yet.<br>Predictions need to be verified to show calibration curve.",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure()
    classes = sorted(df['actual_label'].unique())

    for label in classes:
        # Get predictions for this class
        y_true = (df['actual_label'] == label).astype(int)
        y_prob = df[f'prob_{label}']

        # Create probability bins
        n_bins = 10
        bins = np.linspace(0, 1, n_bins + 1)
        binned = pd.cut(y_prob, bins)

        # Calculate mean predicted prob and true fraction for each bin
        bin_stats = pd.DataFrame({
            'mean_pred_prob': y_prob.groupby(binned).mean(),
            'true_fraction': y_true.groupby(binned).mean(),
            'count': y_true.groupby(binned).count()
        })

        # Add calibration curve
        fig.add_trace(
            go.Scatter(
                x=bin_stats['mean_pred_prob'],
                y=bin_stats['true_fraction'],
                name=label,
                mode='lines+markers',
                text=bin_stats['count'],
                hovertemplate="Pred prob: %{x:.2f}<br>True frac: %{y:.2f}<br>n=%{text}<extra></extra>"
            )
        )

    # Add perfect calibration line
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode='lines',
            line=dict(dash='dash', color='gray'),
            showlegend=False
        )
    )

    fig.update_layout(
        title="Calibration Curves",
        xaxis_title="Mean Predicted Probability",
        yaxis_title="Observed Fraction",
        width=700,
        height=500
    )

    return fig


def plot_rolling_metrics(df: pd.DataFrame, window: int = 7) -> go.Figure:
    """Plot rolling accuracy and other metrics over time.

    Args:
        df: DataFrame with predictions and actuals
        window: Rolling window size in days

    Returns:
        Plotly figure with rolling metrics
    """
    # Compute rolling metrics
    df = df.set_index('timestamp').sort_index()
    rolling_accuracy = (
        df['predicted_label'] == df['actual_label']
    ).rolling(window).mean()

    # Create figure
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=rolling_accuracy.index,
            y=rolling_accuracy.values,
            name=f'{window}-day Rolling Accuracy',
            line=dict(width=2)
        )
    )

    fig.update_layout(
        title=f"Rolling Prediction Accuracy (Window: {window} days)",
        xaxis_title="Date",
        yaxis_title="Accuracy",
        width=800,
        height=400,
        showlegend=True,
        yaxis_range=[0, 1]
    )

    return fig


def plot_backtest_performance(df: pd.DataFrame) -> go.Figure:
    """Plot cumulative returns and drawdown from backtest results.

    Args:
        df: DataFrame with backtest results

    Returns:
        Plotly figure with returns and drawdown subplots
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=("Cumulative Returns", "Drawdown"),
        row_heights=[0.7, 0.3]
    )

    # Plot strategy returns
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['strategy_returns'],
            name='Strategy',
            line=dict(color='#26a69a')
        ),
        row=1, col=1
    )

    # Plot buy-and-hold returns
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['bh_returns'],
            name='Buy & Hold',
            line=dict(color='#b2dfdb', dash='dot')
        ),
        row=1, col=1
    )

    # Plot drawdown
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['drawdown'],
            name='Drawdown',
            fill='tozeroy',
            line=dict(color='#ef5350')
        ),
        row=2, col=1
    )

    fig.update_layout(
        title="Backtest Performance",
        showlegend=True,
        height=800,
        template='plotly_dark'
    )

    return fig


def get_worst_predictions(
    df: pd.DataFrame,
    n: int = 10,
    by: str = 'confidence'
) -> pd.DataFrame:
    """Get worst-performing predictions by confidence or error.

    Args:
        df: DataFrame with predictions
        n: Number of predictions to return
        by: Sort criterion ('confidence' or 'error')

    Returns:
        DataFrame with worst predictions
    """
    if df.empty:
        return pd.DataFrame()

    # Determine which columns are available
    available_cols = df.columns.tolist()
    result_cols = ['timestamp', 'predicted_label']

    # Add optional columns if they exist
    if 'predicted_prob' in available_cols:
        result_cols.append('predicted_prob')
    if 'actual_label' in available_cols:
        result_cols.append('actual_label')
    if 'abs_error' in available_cols:
        result_cols.append('abs_error')
    if 'predicted_price' in available_cols:
        result_cols.append('predicted_price')
    if 'coin' in available_cols:
        result_cols.append('coin')
    if 'timeframe' in available_cols:
        result_cols.append('timeframe')

    if by == 'confidence':
        # High confidence but wrong predictions
        if 'actual_label' in available_cols and 'predicted_prob' in available_cols:
            mask = df['predicted_label'] != df['actual_label']
            if mask.any():
                worst = df[mask].nlargest(n, 'predicted_prob')
            else:
                # No wrong predictions, return lowest confidence
                worst = df.nsmallest(n, 'predicted_prob')
        elif 'predicted_prob' in available_cols:
            # No actual_label, just return lowest confidence
            worst = df.nsmallest(n, 'predicted_prob')
        else:
            # No confidence data, return first n rows
            worst = df.head(n)
    else:
        # Largest absolute errors for regression
        if 'abs_error' in available_cols:
            worst = df.nlargest(n, 'abs_error')
        elif 'predicted_prob' in available_cols:
            # Fallback to confidence if abs_error not available
            worst = df.nsmallest(n, 'predicted_prob')
        else:
            # No error data, return first n rows
            worst = df.head(n)

    # Only return columns that exist
    result_cols = [col for col in result_cols if col in worst.columns]
    if result_cols:
        return worst[result_cols].copy()
    else:
        return worst.copy()


def _generate_mock_predictions(
    coin: str,
    timeframe: str,
    model: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """Generate mock prediction data for testing.

    Args:
        coin: Cryptocurrency symbol
        timeframe: Prediction timeframe
        model: Model name
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with mock predictions
    """
    # Generate dates
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    n = len(dates)

    # Generate predictions
    labels = ['Increase', 'Decrease', 'Constant']
    data = {
        'timestamp': dates,
        'coin': [coin] * n,
        'timeframe': [timeframe] * n,
        'model_name': [model] * n,
        'predicted_label': np.random.choice(labels, n),
        'actual_label': np.random.choice(labels, n),
        'predicted_prob': np.random.uniform(0.6, 1.0, n),
        'actual_price_after_interval': np.random.uniform(30000, 40000, n)
    }

    df = pd.DataFrame(data)

    # Add class probabilities
    for label in labels:
        df[f'prob_{label}'] = np.random.uniform(0, 1, n)

    # Normalize probabilities
    prob_cols = [f'prob_{label}' for label in labels]
    df[prob_cols] = df[prob_cols].div(df[prob_cols].sum(axis=1), axis=0)

    return df


def _generate_mock_backtest(
    coin: str,
    timeframe: str,
    model: str
) -> pd.DataFrame:
    """Generate mock backtest results for testing.

    Args:
        coin: Cryptocurrency symbol
        timeframe: Trading timeframe
        model: Model name

    Returns:
        DataFrame with mock backtest results
    """
    # Generate 90 days of data
    dates = pd.date_range(end=datetime.now(), periods=90, freq='D')
    n = len(dates)

    # Generate cumulative returns with some randomness
    strategy_returns = np.random.normal(0.001, 0.02, n).cumsum()
    bh_returns = np.random.normal(0.0005, 0.015, n).cumsum()

    # Calculate drawdown
    rolling_max = pd.Series(strategy_returns).expanding().max()
    drawdown = (strategy_returns - rolling_max) / rolling_max

    data = {
        'timestamp': dates,
        'strategy_returns': strategy_returns,
        'bh_returns': bh_returns,
        'drawdown': drawdown,
        'trade_pnl': np.random.normal(0.001, 0.01, n)
    }

    return pd.DataFrame(data)
