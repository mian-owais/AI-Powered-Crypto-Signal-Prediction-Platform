"""
Vercel-optimized API for cryptocurrency prediction
Runs as a serverless function with built-in caching
"""

import os
import sys
from pathlib import Path
import json
from datetime import datetime
import pickle

# Add src to path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from flask import Flask, jsonify, request
from src.data_fetcher import fetch_crypto_data
from src.model_train import prepare_training_data, walk_forward_train
from src.feature_engineering import engineer_features

app = Flask(__name__)

# Cache to store models across requests (in-memory for this request)
MODEL_CACHE = {}

def get_or_train_model(crypto="bitcoin", force_retrain=False):
    """Get cached model or train new one"""
    cache_key = f"model_{crypto}"
    
    # Check if model exists in cache
    if cache_key in MODEL_CACHE and not force_retrain:
        return MODEL_CACHE[cache_key]
    
    try:
        # Fetch data
        df = fetch_crypto_data(crypto=crypto, days=365)
        
        if df.empty or len(df) < 10:
            return None, "Not enough data"
        
        # Engineer features
        df = engineer_features(df)
        
        # Prepare data
        X, y, feature_names, prices = prepare_training_data(df)
        
        if X.shape[0] < 2:
            return None, "Insufficient samples after processing"
        
        # Train model (quick training)
        model_results = walk_forward_train(
            X, y,
            n_splits=min(3, len(X) // 10),  # Reduce splits for speed
            verbose=False
        )
        
        # Cache the model
        MODEL_CACHE[cache_key] = {
            "model": model_results.get("best_model"),
            "feature_names": feature_names,
            "metrics": model_results.get("metrics"),
            "timestamp": datetime.now().isoformat()
        }
        
        return MODEL_CACHE[cache_key], "success"
    
    except Exception as e:
        return None, str(e)


@app.route("/", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Crypto Prediction Bot",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route("/api/train", methods=["POST"])
def train():
    """Train or retrain model"""
    try:
        crypto = request.json.get("crypto", "bitcoin") if request.json else "bitcoin"
        force = request.json.get("force_retrain", False) if request.json else False
        
        model_data, status = get_or_train_model(crypto=crypto, force_retrain=force)
        
        if model_data is None:
            return jsonify({"error": status}), 400
        
        return jsonify({
            "status": "success",
            "crypto": crypto,
            "metrics": model_data.get("metrics"),
            "timestamp": model_data.get("timestamp")
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict", methods=["POST"])
def predict():
    """Make prediction"""
    try:
        crypto = request.json.get("crypto", "bitcoin") if request.json else "bitcoin"
        
        # Get model (train if not cached)
        model_data, status = get_or_train_model(crypto=crypto)
        
        if model_data is None:
            return jsonify({"error": status}), 400
        
        model = model_data["model"]
        
        if model is None:
            return jsonify({"error": "Model not available"}), 400
        
        # Get latest data for prediction
        df = fetch_crypto_data(crypto=crypto, days=30)
        df = engineer_features(df)
        
        if df.empty:
            return jsonify({"error": "No data available"}), 400
        
        X, _, feature_names, prices = prepare_training_data(df)
        
        if X.shape[0] == 0:
            return jsonify({"error": "No features available"}), 400
        
        # Get latest data point
        latest_X = X[-1:] if X.shape[0] > 0 else X
        
        # Make prediction
        if hasattr(model, 'predict'):
            pred = model.predict(latest_X)[0]
        else:
            pred = float(model(latest_X)[0])
        
        current_price = float(prices[-1]) if len(prices) > 0 else 0
        price_change = ((pred - current_price) / current_price * 100) if current_price > 0 else 0
        
        return jsonify({
            "status": "success",
            "crypto": crypto,
            "current_price": current_price,
            "predicted_price": float(pred),
            "change_percent": round(price_change, 2),
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def status():
    """Get deployment status"""
    return jsonify({
        "status": "running",
        "models_cached": list(MODEL_CACHE.keys()),
        "timestamp": datetime.now().isoformat()
    }), 200


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
