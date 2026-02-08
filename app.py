from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import os

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Backend is running"

# ---------------- CACHE ----------------
CACHE = {}
CACHE_TTL = timedelta(minutes=5)

# ---------------- STOCK UNIVERSE ----------------
STOCK_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA',
    'AMZN', 'NFLX', 'JPM', 'BAC', 'WFC', 'GS', 'V', 'MA',
    'JNJ', 'UNH', 'PFE', 'ABBV', 'WMT', 'HD', 'NKE', 'MCD',
    'BA', 'CAT', 'UNP', 'XOM', 'CVX', 'COP', 'DIS', 'CMCSA'
]

# ---------------- STOCK ANALYSIS ----------------
def analyze_stock(symbol, filters):
    try:
        stock = yf.Ticker(symbol)

        # Yahoo-safe call
        hist = stock.history(period="3mo", interval="1d")

        if hist.empty or len(hist) < 20:
            return None

        # Anti rate-limit delay
        time.sleep(random.uniform(0.4, 0.8))

        current_price = hist["Close"].iloc[-1]

        # Price filters
        if filters.get("minPrice") and current_price < float(filters["minPrice"]):
            return None
        if filters.get("maxPrice") and current_price > float(filters["maxPrice"]):
            return None

        avg_volume = hist["Volume"].mean() / 1_000_000
        if filters.get("minVolume") and avg_volume < float(filters["minVolume"]):
            return None

        prices = hist["Close"].values

        returns_5d = ((prices[-1] - prices[-5]) / prices[-5]) * 100
        returns_20d = ((prices[-1] - prices[-20]) / prices[-20]) * 100

        score = 50
        if returns_5d > 0:
            score += 10
        if returns_20d > 0:
            score += 15
        if returns_20d > 5:
            score += 10
        if hist["Volume"].iloc[-5:].mean() > hist["Volume"].mean():
            score += 10

        if score < 60:
            return None

        hl_range = (hist["High"] - hist["Low"]).mean()

        entry = round(current_price, 2)
        target = round(entry + (2.2 * hl_range), 2)
        stop = round(entry - (1.3 * hl_range), 2)

        trend = "Bullish" if prices[-5:].mean() > prices[-20:].mean() else "Bearish"

        return {
            "symbol": symbol,
            "name": symbol,
            "score": score,
            "entryPrice": entry,
            "targetPrice": target,
            "stopLoss": stop,
            "trend": trend,
            "volume": f"{avg_volume:.1f}M",
            "momentum": round(returns_20d, 2),
        }

    except Exception as e:
        print(f"Yahoo error for {symbol}: {e}")
        return None

# ---------------- SCAN API ----------------
@app.route("/api/scan", methods=["POST"])
def scan_stocks():
    filters = request.json or {}
    start_time = datetime.now()

    cache_key = str(filters)
    if cache_key in CACHE:
        data, ts = CACHE[cache_key]
        if datetime.now() - ts < CACHE_TTL:
            return jsonify(data)

    results = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(analyze_stock, s, filters) for s in STOCK_UNIVERSE]

        for future in as_completed(futures):
            # Prevent Render worker timeout
            if (datetime.now() - start_time).seconds > 18:
                break

            result = future.result()
            if result:
                results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)
    top_results = results[:10]

    response = {
        "stocks": top_results,
        "totalScanned": len(STOCK_UNIVERSE),
        "totalFound": len(top_results),
        "timestamp": datetime.now().isoformat()
    }

    CACHE[cache_key] = (response, datetime.now())
    return jsonify(response)

# ---------------- HEALTH ----------------
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "stocksAvailable": len(STOCK_UNIVERSE),
        "timestamp": datetime.now().isoformat()
    })

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
