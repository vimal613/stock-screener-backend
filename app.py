from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import time
import os

app = Flask(__name__)
CORS(app)

IST = pytz.timezone("Asia/Kolkata")

# -------------------------------
# STOCK UNIVERSES
# -------------------------------
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
    "WIPRO.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TECHM.NS",
    "M&M.NS", "TATAMOTORS.NS", "BAJAJFINSV.NS", "TATASTEEL.NS", "ADANIENT.NS",
    "COALINDIA.NS", "INDUSINDBK.NS", "DIVISLAB.NS", "DRREDDY.NS", "CIPLA.NS",
    "EICHERMOT.NS", "HEROMOTOCO.NS", "BRITANNIA.NS", "GRASIM.NS", "HINDALCO.NS",
    "JSWSTEEL.NS", "APOLLOHOSP.NS", "BAJAJ-AUTO.NS", "TATACONSUM.NS", "BPCL.NS",
    "ADANIPORTS.NS", "SHREECEM.NS", "UPL.NS", "LTIM.NS", "SBILIFE.NS"
]

# Small MIDCAP sample (expand later safely)
MIDCAP = [
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS",
    "LUPIN.NS", "TORNTPHARM.NS", "ALKEM.NS",
    "AUBANK.NS", "PAGEIND.NS", "MPHASIS.NS"
]

# -------------------------------
# SAFE STOCK ANALYSIS
# -------------------------------
def analyze_stock(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="7d", interval="1d")

        if hist.empty or len(hist) < 5:
            return None

        close = hist["Close"].values
        high = hist["High"].values
        low = hist["Low"].values
        volume = hist["Volume"].values

        current_price = float(close[-1])
        price_5d_ago = float(close[0])

        move_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100

        if move_5d < 0.5 or move_5d > 2.5:
            return None

        green_days = sum(1 for i in range(1, 5) if close[i] > close[i-1])
        if green_days < 3:
            return None

        avg_volume = volume.mean()
        if volume[-1] < avg_volume * 0.8:
            return None

        avg_range = ((high - low) / close).mean() * 100
        if avg_range < 0.5 or avg_range > 1.5:
            return None

        target = round(current_price * 1.025, 2)
        stop = round(current_price * 0.99, 2)

        rr = (target - current_price) / (current_price - stop)
        if rr < 2:
            return None

        return {
            "symbol": symbol.replace(".NS", ""),
            "price": round(current_price, 2),
            "target": target,
            "stop": stop,
            "move5d": round(move_5d, 2),
            "greenDays": green_days,
            "riskReward": round(rr, 2)
        }

    except Exception:
        return None


# -------------------------------
# SCAN ENDPOINT
# -------------------------------
@app.route("/api/scan", methods=["POST"])
def scan():
    data = request.json or {}

    universe = data.get("universe", "NIFTY50")
    capital = float(data.get("capital", 50000))

    stocks = NIFTY_50 if universe == "NIFTY50" else MIDCAP

    results = []
    scanned = 0

    for s in stocks:
        scanned += 1
        r = analyze_stock(s)
        if r:
            qty = int((capital * 0.95) / r["price"])
            r["quantity"] = qty
            r["investment"] = round(qty * r["price"], 2)
            r["maxProfit"] = round(qty * (r["target"] - r["price"]), 2)
            r["maxLoss"] = round(qty * (r["price"] - r["stop"]), 2)
            results.append(r)

        time.sleep(0.7)  # Yahoo safety

    results = sorted(results, key=lambda x: x["riskReward"], reverse=True)

    return jsonify({
        "status": "TRADE" if results else "NO_TRADE",
        "timestamp": datetime.now(IST).isoformat(),
        "scanned": scanned,
        "found": len(results),
        "results": results[:10]  # show ALL valid, top first
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/")
def home():
    return "Alpha Screener Backend Running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
