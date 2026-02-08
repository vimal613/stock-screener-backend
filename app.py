from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)
@app.route("/")
def home():
    return "Backend is running"


# Stock universe to scan
STOCK_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA',
    'AMZN', 'NFLX', 'JPM', 'BAC', 'WFC', 'GS', 'V', 'MA',
    'JNJ', 'UNH', 'PFE', 'ABBV', 'WMT', 'HD', 'NKE', 'MCD',
    'BA', 'CAT', 'UNP', 'XOM', 'CVX', 'COP', 'DIS', 'CMCSA'
]

def analyze_stock(symbol, filters):
    """Analyze a single stock using yfinance data"""
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        hist = stock.history(period='3mo')
        
        if hist.empty or len(hist) < 20:
            return None
        
        # Get current data
        current_price = hist['Close'].iloc[-1]
        
        # Apply filters
        if filters.get('minPrice') and current_price < float(filters['minPrice']):
            return None
        if filters.get('maxPrice') and current_price > float(filters['maxPrice']):
            return None
        
        avg_volume = hist['Volume'].mean() / 1_000_000
        if filters.get('minVolume') and avg_volume < float(filters['minVolume']):
            return None
        
        market_cap = info.get('marketCap', 0) / 1_000_000_000
        if filters.get('minMarketCap') and market_cap < float(filters['minMarketCap']):
            return None
        if filters.get('maxMarketCap') and market_cap > float(filters['maxMarketCap']):
            return None
        
        # Calculate simple metrics
        prices = hist['Close'].values
        
        # Calculate returns
        returns_5d = ((prices[-1] - prices[-5]) / prices[-5]) * 100 if len(prices) >= 5 else 0
        returns_20d = ((prices[-1] - prices[-20]) / prices[-20]) * 100 if len(prices) >= 20 else 0
        
        # Simple scoring (0-100)
        score = 50  # Base score
        
        # Positive momentum
        if returns_5d > 2:
            score += 15
        elif returns_5d > 0:
            score += 10
        
        if returns_20d > 5:
            score += 20
        elif returns_20d > 0:
            score += 10
        
        # Volume check
        recent_vol = hist['Volume'].iloc[-5:].mean()
        avg_vol = hist['Volume'].mean()
        if recent_vol > avg_vol * 1.2:
            score += 15
        
        # Only return stocks with score >= 60
        if score < 60:
            return None
        
        # Calculate targets using simple ATR approximation
        high_low_range = (hist['High'] - hist['Low']).mean()
        
        entry_price = round(current_price, 2)
        target_price = round(current_price + (2.5 * high_low_range), 2)
        stop_loss = round(current_price - (1.5 * high_low_range), 2)
        
        # Estimate target date
        if returns_20d > 10:
            days = 30
        elif returns_20d > 5:
            days = 60
        else:
            days = 90
        
        target_date = (datetime.now() + timedelta(days=days)).strftime('%b %d, %Y')
        
        # Determine trend
        ma_short = prices[-5:].mean() if len(prices) >= 5 else current_price
        ma_long = prices[-20:].mean() if len(prices) >= 20 else current_price
        trend = 'Bullish' if ma_short > ma_long else 'Bearish'
        
        return {
            'symbol': symbol,
            'name': info.get('longName', symbol),
            'score': int(score),
            'entryPrice': entry_price,
            'targetPrice': target_price,
            'stopLoss': stop_loss,
            'targetDate': target_date,
            'volume': f"{avg_volume:.1f}M",
            'marketCap': f"{market_cap:.1f}B" if market_cap > 0 else 'N/A',
            'rsi': round(50 + (returns_5d * 2), 2),  # Simplified RSI approximation
            'trend': trend,
            'peRatio': round(info.get('forwardPE', 0), 2) if info.get('forwardPE') else 'N/A',
            'momentum': round(returns_20d, 2),
            'sector': info.get('sector', 'Unknown')
        }
        
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

@app.route('/api/scan', methods=['POST'])
def scan_stocks():
    """Scan stocks with filters"""
    try:
        filters = request.json or {}
        results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(analyze_stock, symbol, filters): symbol 
                      for symbol in STOCK_UNIVERSE}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        top_results = results[:10]
        
        return jsonify({
            'stocks': top_results,
            'totalScanned': len(STOCK_UNIVERSE),
            'totalFound': len(top_results),
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'stocksAvailable': len(STOCK_UNIVERSE),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

