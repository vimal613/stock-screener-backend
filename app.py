from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime
import pytz
import time
import os

app = Flask(__name__)
CORS(app)

# ---------------- BASIC ROUTES ----------------
@app.route("/")
def home():
    return "Indian Trading Backend Running - TEST MODE"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

# ---------------- TIME ----------------
IST = pytz.timezone("Asia/Kolkata")

def market_time_ok():
    return True  # FORCE ENABLED FOR TESTING

# ---------------- STOCK UNIVERSE ----------------
STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS"
]

# ---------------- CORE ANALYSIS (VISIBILITY MODE) ----------------
def analyze_stock(symbol, min_price=None, max_price=None):
    try:
        data = yf.download(
            symbol,
            period="1mo",
            interval="1d",
            progress=False,
            threads=False
        )

        if data.empty:
            return None

        price = round(data["Close"].iloc[-1], 2)

        # Optional price range filter
        if min_price is not None and price < min_price:
            return None
        if max_price is not None and price > max_price:
            return None

        # VISIBILITY MODE → accept all valid Yahoo data
        return {
            "symbol": symbol.replace(".NS", ""),
            "price": price
        }

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# ---------------- SCAN API ----------------
@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    if not market_time_ok():
        return jsonify({
            "marketStatus": "NO_TRADE_TODAY",
            "reason": "Outside scan time"
        })

    filters = request.json or {}
    min_price = float(filters["minPrice"]) if filters.get("minPrice") else None
    max_price = float(filters["maxPrice"]) if filters.get("maxPrice") else None

    results = []

    for symbol in STOCKS:
        stock = analyze_stock(symbol, min_price, max_price)
        if stock:
            results.append(stock)
        time.sleep(1.2)  # Yahoo safety

    return jsonify({
        "marketStatus": "TRADE",
        "note": "VISIBILITY MODE - Strategy filters disabled",
        "validSetups": [s["symbol"] for s in results],
        "topPicks": [
            {
                "symbol": s["symbol"],
                "entry": "MARKET",
                "targetPercent": 2.2,
                "stopLossPercent": -1.0,
                "maxHoldDays": 5,
                "confidence": "TEST"
            }
            for s in results[:3]
        ]
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
