from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Stock Screener Backend - MOCK DATA MODE"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

# ---------------- MOCK NIFTY DATA ----------------
# This simulates what real market data would look like
MOCK_STOCKS = [
    {"symbol": "RELIANCE", "price": 2894, "avgMove": 0.8},
    {"symbol": "TCS", "price": 4120, "avgMove": 0.6},
    {"symbol": "INFY", "price": 1652, "avgMove": 1.1},
    {"symbol": "HDFCBANK", "price": 1540, "avgMove": 0.5},
    {"symbol": "ICICIBANK", "price": 1045, "avgMove": 0.9},
]

@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    filters = request.json or {}
    min_price = float(filters["minPrice"]) if filters.get("minPrice") else None
    max_price = float(filters["maxPrice"]) if filters.get("maxPrice") else None

    valid = []

    for s in MOCK_STOCKS:
        if min_price and s["price"] < min_price:
            continue
        if max_price and s["price"] > max_price:
            continue

        # 5-day strategy logic
        if 0.4 <= s["avgMove"] <= 1.5:
            valid.append(s)

    top_picks = valid[:3]

    return jsonify({
        "marketStatus": "TRADE" if valid else "NO_TRADE_TODAY",
        "note": "MOCK MODE - Strategy logic validated",
        "validSetups": valid,
        "topPicks": [
            {
                "symbol": s["symbol"],
                "entry": "MARKET",
                "targetPercent": 2.0,
                "stopLossPercent": -1.0,
                "holdDays": 5,
                "confidence": "HIGH"
            }
            for s in top_picks
        ],
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
