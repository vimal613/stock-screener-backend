from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime
import pytz
import os
import time

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Backend running - DEBUG VISIBILITY MODE"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

IST = pytz.timezone("Asia/Kolkata")

def market_time_ok():
    return True  # FORCE ON

STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS"
]

def analyze_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        # EVEN if only 1 candle exists
        if hist is None or len(hist) == 0:
            return None

        price = round(hist["Close"].iloc[-1], 2)

        return {
            "symbol": symbol.replace(".NS", ""),
            "price": price,
            "dataPoints": len(hist)
        }

    except Exception as e:
        print("Yahoo error:", symbol, e)
        return None

@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    results = []

    for symbol in STOCKS:
        stock = analyze_stock(symbol)
        if stock:
            results.append(stock)
        time.sleep(1.2)  # Yahoo protection

    return jsonify({
        "marketStatus": "TRADE",
        "note": "DEBUG MODE - Showing all Yahoo data",
        "validSetups": results,
        "topPicks": [
            {
                "symbol": s["symbol"],
                "entry": "MARKET",
                "targetPercent": 2.0,
                "stopLossPercent": -1.0,
                "holdDays": 5
            }
            for s in results[:3]
        ]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
