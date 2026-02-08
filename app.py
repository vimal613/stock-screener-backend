from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os

app = Flask(__name__)

# 🔴 IMPORTANT: Explicit CORS for API routes (fixes Failed to fetch)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------------- BASIC ----------------
@app.route("/")
def home():
    return "Backend is running"

# ---------------- STOCK UNIVERSE ----------------
STOCK_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "TSLA",
    "AMZN", "NFLX", "JPM", "BAC", "WFC", "GS", "V", "MA",
    "JNJ", "UNH", "PFE", "ABBV", "WMT", "HD", "NKE", "MCD",
    "BA", "CAT", "UNP", "XOM", "CVX", "COP", "DIS", "CMCSA"
]

# ---------------- CACHE ----------------
SCAN_CACHE = {}
SCAN_TTL = timedelta(minutes=5)

# ---------------- UTILITIES ----------------
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ---------------- ANALYSIS ----------------
def analyze_stock(data, symbol, filters):
    try:
        hist = data[symbol].dropna()
        if len(hist) < 20:
            return None

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        current_price = close.iloc[-1]

        # Filters
        if filters.get("minPrice") and current_price < float(filters["minPrice"]):
            return None
        if filters.get("maxPrice") and current_price > float(filters["maxPrice"]):
            return None

        avg_volume = volume.mean() / 1_000_000
        if filters.get("minVolume") and avg_volume < float(filters["minVolume"]):
            return None

        returns_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
        returns_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100

        rsi = calculate_rsi(close).iloc[-1]
        hl_range = (high - low).mean()

        score = 50
        if returns_5d > 0: score += 10
        if returns_20d > 0: score += 15
        if returns_20d > 5: score += 10
        if rsi < 70: score += 10

        if score < 60:
            return None

        entry = round(current_price, 2)
        target = round(entry + 2.2 * hl_range, 2)
        stop = round(entry - 1.3 * hl_range, 2)

        days = 30 if returns_20d > 10 else 60 if returns_20d > 5 else 90
        target_date = (datetime.now() + timedelta(days=days)).strftime("%b %d, %Y")

        trend = "Bullish" if close.iloc[-5:].mean() > close.iloc[-20:].mean() else "Bearish"

        return {
            "symbol": symbol,
            "name": symbol,
            "score": score,
            "entryPrice": entry,
            "targetPrice": target,
            "stopLoss": stop,
            "targetDate": target_date,
            "volume": f"{avg_volume:.1f}M",
            "marketCap": "N/A",
            "rsi": round(rsi, 2),
            "trend": trend,
            "peRatio": "N/A",
            "momentum": round(returns_20d, 2),
        }

    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

# ---------------- SCAN API ----------------
# 🔴 IMPORTANT: OPTIONS added (fixes browser preflight)
@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan_stocks():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"})

    filters = request.json or {}
    cache_key = str(filters)

    if cache_key in SCAN_CACHE:
        data, ts = SCAN_CACHE[cache_key]
        if datetime.now() - ts < SCAN_TTL:
            return jsonify(data)

    # 🔥 ONE Yahoo call (batch)
    data = yf.download(
        tickers=STOCK_UNIVERSE,
        period="3mo",
        interval="1d",
        group_by="ticker",
        threads=False,
        progress=False
    )

    results = []
    for symbol in STOCK_UNIVERSE:
        if symbol in data:
            stock = analyze_stock(data, symbol, filters)
            if stock:
                results.append(stock)

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:10]

    response = {
        "stocks": top,
        "totalScanned": len(STOCK_UNIVERSE),
        "totalFound": len(top),
        "timestamp": datetime.now().isoformat()
    }

    SCAN_CACHE[cache_key] = (response, datetime.now())
    return jsonify(response)

# ---------------- HEALTH ----------------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
