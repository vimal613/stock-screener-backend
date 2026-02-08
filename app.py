from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import os
import time

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.route("/")
def home():
    return "Backend running"

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

# 🔹 SMALL UNIVERSE (Render-safe)
STOCK_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "TSLA", "META",
    "AMZN", "GOOGL", "NFLX", "AMD", "INTC"
]

def analyze_stock(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1mo")  # 🔥 SHORT PERIOD

        if hist.empty or len(hist) < 10:
            return None

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        price = round(close.iloc[-1], 2)
        returns_10 = (price - close.iloc[-10]) / close.iloc[-10] * 100

        score = 50
        if returns_10 > 0:
            score += 20
        if volume.iloc[-1] > volume.mean():
            score += 15

        if score < 60:
            return None

        atr = (high - low).mean()
        target = round(price + atr * 2, 2)
        stop = round(price - atr * 1.2, 2)

        return {
            "symbol": symbol,
            "name": symbol,
            "score": score,
            "entryPrice": price,
            "targetPrice": target,
            "stopLoss": stop,
            "targetDate": (datetime.now() + timedelta(days=30)).strftime("%b %d, %Y"),
            "volume": "OK",
            "marketCap": "N/A",
            "rsi": 50,
            "trend": "Bullish" if returns_10 > 0 else "Bearish",
            "peRatio": "N/A",
            "momentum": round(returns_10, 2),
        }

    except Exception as e:
        print(f"{symbol} failed:", e)
        return None

@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    results = []

    for symbol in STOCK_UNIVERSE:
        stock = analyze_stock(symbol)
        if stock:
            results.append(stock)
        time.sleep(0.5)  # 🔥 throttle Yahoo (VERY IMPORTANT)

    results.sort(key=lambda x: x["score"], reverse=True)

    return jsonify({
        "stocks": results,
        "totalScanned": len(STOCK_UNIVERSE),
        "totalFound": len(results),
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
