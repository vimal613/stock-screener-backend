from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime
import pytz
import time
import os

app = Flask(__name__)
CORS(app)

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return "Indian Trading Backend Running - VISIBILITY MODE"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

# ---------------- TIME ----------------
IST = pytz.timezone("Asia/Kolkata")

def market_time_ok():
    return True  # forced ON for testing

# ---------------- STOCK UNIVERSE ----------------
STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS"
]

# ---------------- ANALYSIS (RENDER SAFE) ----------------
def analyze_stock(symbol, min_price=None, max_price=None):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")

        if hist.empty:
            return None

        price = round(hist["Close"].iloc[-1], 2)

        if min_price is not None and price < min_price:
            return None
        if max_price is not None and price > max_price:
            return None

        return {
            "symbol": symbol.replace(".NS", ""),
            "price": price
        }

    except Exception as e:
        print(f"Yahoo error {symbol}: {e}")
        return None

# ---------------- SCAN ----------------
@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    if not market_time_ok():
        return jsonify({
            "marketStatus": "NO_TRADE_TODAY",
            "reason": "Outside scan window"
        })

    filters = request.json or {}
    min_price = float(filters["minPrice"]) if filters.get("minPrice") else None
    max_price = float(filters["maxPrice"]) if filters.get("maxPrice") else None

    results = []

    for symbol in STOCKS:
        stock = analyze_stock(symbol, min_price, max_price)
        if stock:
            results.append(stock)
        time.sleep(1.5)  # Yahoo protection

    return jsonify({
        "marketStatus": "TRADE",
        "note": "VISIBILITY MODE - Yahoo single-symbol safe",
        "validSetups": [s["symbol"] for s in results],
        "topPicks": [
            {
                "symbol": s["symbol"],
                "entry": "MARKET",
                "targetPercent": 2.0,
                "stopLossPercent": -1.0,
                "holdDays": 5,
                "confidence": "TEST"
            }
            for s in results[:3]
        ]
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
