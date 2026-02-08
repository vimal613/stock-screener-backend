from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime
import time
import os

app = Flask(__name__)
CORS(app)

# -------------------------
# BASIC ROUTES
# -------------------------
@app.route("/")
def home():
    return "Stock Screener API running"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

# -------------------------
# NIFTY-STYLE STOCK LIST
# (Safe count for Yahoo)
# -------------------------
STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "LT.NS",
    "ITC.NS",
    "SBIN.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS"
]

# -------------------------
# SIMPLE, SAFE ANALYSIS
# -------------------------
def analyze_stock(symbol):
    try:
        stock = yf.Ticker(symbol)

        # last 10 trading days only (safe)
        hist = stock.history(period="10d", interval="1d")

        if hist.empty or len(hist) < 5:
            return None

        close_prices = hist["Close"].values

        # 5-day move %
        start_price = close_prices[-5]
        end_price = close_prices[-1]
        move_pct = ((end_price - start_price) / start_price) * 100

        # filter small but usable moves
        if move_pct < 0.3 or move_pct > 3:
            return None

        return {
            "symbol": symbol.replace(".NS", ""),
            "price": round(float(end_price), 2),
            "avgMove": round(move_pct, 2)
        }

    except Exception:
        return None

# -------------------------
# MAIN SCAN API
# -------------------------
@app.route("/api/scan", methods=["POST"])
def scan():
    results = []

    for symbol in STOCKS:
        data = analyze_stock(symbol)
        if data:
            results.append(data)

        # IMPORTANT: prevent Yahoo rate-limit
        time.sleep(1)

    # Sort by strongest move
    results = sorted(results, key=lambda x: x["avgMove"], reverse=True)

    # Top picks (max 3)
    top_picks = []
    for r in results[:3]:
        top_picks.append({
            "symbol": r["symbol"],
            "confidence": "HIGH",
            "entry": "MARKET",
            "holdDays": 5,
            "stopLossPercent": -1,
            "expectedMovePercent": round(r["avgMove"], 2)
        })

    return jsonify({
        "marketStatus": "TRADE" if top_picks else "NO_TRADE",
        "note": "LIVE MODE - Yahoo safe scan",
        "timestamp": datetime.utcnow().isoformat(),
        "topPicks": top_picks,
        "validSetups": results
    })

# -------------------------
# RENDER PORT BINDING
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
