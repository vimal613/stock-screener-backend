from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import time
import statistics
import os

app = Flask(__name__)
CORS(app)

# ============================================
# INDIAN TIMEZONE
# ============================================
IST = pytz.timezone("Asia/Kolkata")

# ============================================
# NIFTY-50 STOCK UNIVERSE
# ============================================
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

# ============================================
# MARKET TIMING CHECK
# ============================================
def is_market_time():
    """Check if current time is in allowed scan window"""
    now = datetime.now(IST)
    current_time = now.time()
    
    # Market hours: 10:45 AM - 1:30 PM IST
    start_time = datetime.strptime("10:45", "%H:%M").time()
    end_time = datetime.strptime("13:30", "%H:%M").time()
    
    # Check if weekday (Mon-Fri)
    is_weekday = now.weekday() < 5
    
    # Check if in time window
    is_valid_time = start_time <= current_time <= end_time
    
    return is_weekday and is_valid_time

# ============================================
# STOCK ANALYSIS FUNCTION
# ============================================
def analyze_stock(symbol, min_price=None, max_price=None):
    """
    Analyze a single stock for 5-day momentum strategy
    Returns dict with trade data or None if rejected
    """
    try:
        # Fetch stock data
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="10d", interval="1d")
        
        # Data validation
        if hist.empty or len(hist) < 7:
            return None
        
        # Get price data
        close_prices = hist["Close"].values
        volumes = hist["Volume"].values
        high_prices = hist["High"].values
        low_prices = hist["Low"].values
        
        current_price = float(close_prices[-1])
        
        # FILTER 1: Price Range (optional)
        if min_price and current_price < min_price:
            return None
        if max_price and current_price > max_price:
            return None
        
        # FILTER 2: 5-Day Movement (0.5% to 2.5%)
        price_5d_ago = close_prices[-6]
        movement_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
        
        if movement_5d < 0.5 or movement_5d > 2.5:
            return None
        
        # FILTER 3: Daily Movement Pattern (smooth, not wild)
        daily_moves = []
        for i in range(-5, 0):
            daily_move = abs((close_prices[i] - close_prices[i-1]) / close_prices[i-1] * 100)
            daily_moves.append(daily_move)
        
        avg_daily_move = statistics.mean(daily_moves)
        
        if avg_daily_move < 0.3 or avg_daily_move > 0.8:
            return None
        
        # FILTER 4: No Single-Day Spikes (< 2%)
        max_daily_move = max(daily_moves)
        if max_daily_move > 2.0:
            return None
        
        # FILTER 5: Green Days (at least 3 out of 5)
        green_days = sum(1 for i in range(-5, 0) if close_prices[i] > close_prices[i-1])
        if green_days < 3:
            return None
        
        # FILTER 6: Volume Confirmation (>= 80% of average)
        avg_volume = statistics.mean(volumes[-10:])
        current_volume = volumes[-1]
        
        if current_volume < (avg_volume * 0.8):
            return None
        
        # FILTER 7: Volatility Check (0.5% - 1.5%)
        daily_ranges = [(high_prices[i] - low_prices[i]) / close_prices[i] * 100 
                       for i in range(-5, 0)]
        avg_volatility = statistics.mean(daily_ranges)
        
        if avg_volatility < 0.5 or avg_volatility > 1.5:
            return None
        
        # CALCULATE TRADE PARAMETERS
        target_price = round(current_price * 1.025, 2)  # +2.5%
        stop_loss = round(current_price * 0.99, 2)      # -1%
        
        # Calculate exit date (5 trading days from now)
        exit_date = datetime.now(IST) + timedelta(days=7)
        exit_date_str = exit_date.strftime("%b %d, %Y")
        
        # Risk/Reward Ratio
        profit_potential = target_price - current_price
        loss_potential = current_price - stop_loss
        risk_reward = profit_potential / loss_potential if loss_potential > 0 else 0
        
        # FILTER 8: Minimum Risk/Reward (2:1)
        if risk_reward < 2.0:
            return None
        
        # Stock PASSED all filters
        return {
            "symbol": symbol.replace(".NS", ""),
            "currentPrice": round(current_price, 2),
            "targetPrice": target_price,
            "stopLoss": stop_loss,
            "movement5d": round(movement_5d, 2),
            "avgDailyMove": round(avg_daily_move, 2),
            "volatility": round(avg_volatility, 2),
            "riskReward": round(risk_reward, 2),
            "exitDate": exit_date_str,
            "greenDays": green_days,
            "volumeConfirmed": current_volume > avg_volume
        }
        
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

# ============================================
# RANK STOCKS BY QUALITY
# ============================================
def rank_stocks(stocks):
    """
    Rank stocks by quality score
    Higher score = better trade setup
    """
    for stock in stocks:
        score = 0
        
        # Smoothness (lower volatility = better)
        if stock["volatility"] < 0.7:
            score += 30
        elif stock["volatility"] < 1.0:
            score += 20
        else:
            score += 10
        
        # Risk/Reward
        if stock["riskReward"] > 2.5:
            score += 30
        elif stock["riskReward"] > 2.2:
            score += 20
        else:
            score += 10
        
        # Movement strength
        if 1.0 <= stock["movement5d"] <= 1.8:
            score += 25
        elif 0.8 <= stock["movement5d"] < 1.0:
            score += 20
        else:
            score += 15
        
        # Green days
        if stock["greenDays"] >= 4:
            score += 15
        else:
            score += 10
        
        stock["qualityScore"] = score
    
    # Sort by quality score
    return sorted(stocks, key=lambda x: x["qualityScore"], reverse=True)

# ============================================
# CALCULATE CAPITAL ALLOCATION
# ============================================
def calculate_position(stock, capital):
    """Calculate how many shares to buy with given capital"""
    price = stock["currentPrice"]
    
    # Use 95% of capital (keep 5% buffer)
    usable_capital = capital * 0.95
    
    # Calculate quantity
    quantity = int(usable_capital / price)
    
    # Calculate actual investment
    investment = quantity * price
    
    # Calculate P&L
    profit_per_share = stock["targetPrice"] - price
    loss_per_share = price - stock["stopLoss"]
    
    max_profit = round(quantity * profit_per_share, 2)
    max_loss = round(quantity * loss_per_share, 2)
    
    return {
        "quantity": quantity,
        "investment": round(investment, 2),
        "maxProfit": max_profit,
        "maxLoss": max_loss,
        "targetPercent": 2.5,
        "stopPercent": -1.0
    }

# ============================================
# MAIN SCAN ENDPOINT
# ============================================
@app.route("/api/scan", methods=["POST", "OPTIONS"])
def scan_market():
    """Main scanner endpoint"""
    
    if request.method == "OPTIONS":
        return jsonify({"ok": True})
    
    # Check market timing
    if not is_market_time():
        now = datetime.now(IST)
        return jsonify({
            "status": "BLOCKED",
            "reason": "OUTSIDE_SCAN_HOURS",
            "message": "Scan only allowed 10:45 AM - 1:30 PM IST",
            "currentTime": now.strftime("%I:%M %p IST"),
            "isWeekend": now.weekday() >= 5
        })
    
    # Get filters from request
    data = request.json or {}
    capital = float(data.get("capital", 50000))
    min_price = float(data["minPrice"]) if data.get("minPrice") else None
    max_price = float(data["maxPrice"]) if data.get("maxPrice") else None
    
    # Scan all NIFTY-50 stocks
    valid_stocks = []
    scanned_count = 0
    
    for symbol in NIFTY_50:
        scanned_count += 1
        stock = analyze_stock(symbol, min_price, max_price)
        
        if stock:
            valid_stocks.append(stock)
        
        # Rate limit protection
        time.sleep(0.8)
    
    # Rank stocks
    ranked_stocks = rank_stocks(valid_stocks)
    
    # Get top 3
    top_picks = ranked_stocks[:3]
    
    # Add capital allocation to top picks
    for stock in top_picks:
        position = calculate_position(stock, capital)
        stock.update(position)
        
        # Add confidence level
        if stock["qualityScore"] >= 85:
            stock["confidence"] = "HIGH"
            stock["stars"] = 3
        elif stock["qualityScore"] >= 70:
            stock["confidence"] = "GOOD"
            stock["stars"] = 2
        else:
            stock["confidence"] = "MODERATE"
            stock["stars"] = 1
    
    # Determine market status
    if len(top_picks) == 0:
        market_status = "NO_TRADE"
        message = "No high-probability setups today. Capital protection mode."
    else:
        market_status = "TRADE"
        message = f"Found {len(top_picks)} quality trade setup(s)"
    
    # Return response
    return jsonify({
        "status": market_status,
        "message": message,
        "scanTime": datetime.now(IST).strftime("%I:%M %p IST"),
        "scannedStocks": scanned_count,
        "passedFilters": len(valid_stocks),
        "topPicks": top_picks,
        "allValidSetups": [s["symbol"] for s in ranked_stocks]
    })

# ============================================
# HEALTH CHECK
# ============================================
@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "time": datetime.now(IST).strftime("%I:%M %p IST"),
        "marketTime": is_market_time()
    })

# ============================================
# ROOT
# ============================================
@app.route("/")
def home():
    return "Alpha Screener API - Running"

# ============================================
# RUN SERVER
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
