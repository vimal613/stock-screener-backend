from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime
import pytz
import time
import statistics
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------------- BASIC ROUTES ----------------
@app.route("/")
def home():
    return "Indian Trading Backend Running"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

# ---------------- TIME (IST) ----------------
IST = pytz.timezone("Asia/Kolkata")

def market_time_ok():
    return True  # ✅ TEST MODE (IMPORTANT)

# ---------------- NIFTY STOCKS (SMALL SET FOR STABILITY) ----------------
NIFTY_50 = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS"
]

# ---------------- CORE ANALYSIS ----------------
def analyze_stock(symbol, min_price=None, max_price=None):
    try:
        data = yf.download(
            symbol,
            period="1mo",
            interval="1d",
            progress=False,
            threads=False
        )

        if data.empty or len(data) < 7:
            return None

        close = data["Close"].tolist()
        volume = data["Volume"].tolist()

        price = round(close[-1], 2)

        # Optional price range filter
        if min_price and price < min_price:
            return None
        if max_price and price > max_price:
            return None

        # Reject hype spikes (>3.5% in last 3 days)
        daily_moves = [(close[i] - close[i-1]) / close[i-1] * 100 for i in range(1, len(close))]
        if max(daily_moves[-3:]) > 3.5:
            return None

        # Momentum rules
        green_days = sum(1 for i in range(-5, -1) if close[i] > close[i-1])
        if green_days < 3:
            return None

        avg_move = statistics.mean(abs(x) for x in daily_moves[-5:])
        if avg_move < 0.4 or avg_move > 1.5:
            return None

        # Volume confirmation
        if volume[-1] < statistics.mean(volume[-10:]):
            return None

        return {
            "symbol": symbol.replace(".NS", ""),
            "price": price
        }

    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

# ---------------- SCAN API ----------------
@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    if not market_time_ok():
        return jsonify({
            "marketStatus": "NO_TRADE_TODAY",
            "reason": "Outside allowed scan time"
        })

    filters = request.json or {}
    min_price = float(filters["minPrice"]) if filters.get("minPrice") else None
    max_price = float(filters["maxPrice"]) if filters.get("maxPrice") else None

    valid = []

    for symbol in NIFTY_50:
        stock = analyze_stock(symbol, min_price, max_price)
        if stock:
            valid.append(stock)
        time.sleep(1.2)  # Yahoo rate-limit safety

    # ---------------- TEST MODE RESPONSE ----------------
    if len(valid) < 3:
        return jsonify({
            "marketStatus": "TRADE",
            "note": "TEST MODE: Showing partial setups",
            "validSetups": [v["symbol"] for v in valid],
            "topPicks": [
                {
                    "symbol": v["symbol"],
                    "entry": "MARKET",
                    "targetPercent": 2.2,
                    "stopLossPercent": -1.0,
                    "maxHoldDays": 5,
                    "confidence": "LOW"
                }
                for v in valid
            ]
        })

    # ---------------- NORMAL MODE ----------------
    valid.sort(key=lambda x: x["price"])
    top_picks = valid[:3]

    return jsonify({
        "marketStatus": "TRADE",
        "scanTime": datetime.now(IST).strftime("%I:%M %p IST"),
        "validSetups": [v["symbol"] for v in valid],
        "topPicks": [
            {
                "symbol": v["symbol"],
                "entry": "MARKET",
                "targetPercent": 2.2,
                "stopLossPercent": -1.0,
                "maxHoldDays": 5,
                "confidence": "HIGH" if i == 0 else "MEDIUM"
            }
            for i, v in enumerate(top_picks)
        ]
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
