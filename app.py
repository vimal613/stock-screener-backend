from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)
CORS(app)

# List of popular stocks to scan (you can expand this)
STOCK_UNIVERSE = [
    # Technology
    'AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'CSCO', 'ORCL', 'ADBE',
    'CRM', 'AVGO', 'TXN', 'QCOM', 'NOW', 'INTU', 'AMAT', 'MU', 'NFLX', 'PYPL',
    # Healthcare
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY', 'AMGN', 'GILD',
    # Financial
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP', 'USB',
    # Consumer
    'AMZN', 'TSLA', 'WMT', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW', 'COST',
    # Industrial
    'BA', 'CAT', 'HON', 'UNP', 'GE', 'MMM', 'LMT', 'RTX', 'DE', 'UPS',
    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL'
]

def calculate_technical_indicators(df):
    """Calculate comprehensive technical indicators"""
    try:
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        # Moving Averages
        df['SMA_20'] = ta.trend.SMAIndicator(df['Close'], window=20).sma_indicator()
        df['SMA_50'] = ta.trend.SMAIndicator(df['Close'], window=50).sma_indicator()
        df['SMA_200'] = ta.trend.SMAIndicator(df['Close'], window=200).sma_indicator()
        df['EMA_12'] = ta.trend.EMAIndicator(df['Close'], window=12).ema_indicator()
        df['EMA_26'] = ta.trend.EMAIndicator(df['Close'], window=26).ema_indicator()
        
        # Bollinger Bands
        bollinger = ta.volatility.BollingerBands(df['Close'])
        df['BB_Upper'] = bollinger.bollinger_hband()
        df['BB_Lower'] = bollinger.bollinger_lband()
        df['BB_Middle'] = bollinger.bollinger_mavg()
        
        # ATR for volatility
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
        
        # ADX (Trend Strength)
        adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
        df['ADX'] = adx.adx()
        
        # OBV (Volume indicator)
        df['OBV'] = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume']).on_balance_volume()
        
        return df
    except Exception as e:
        print(f"Error calculating indicators: {e}")
        return df

def calculate_score(df, info):
    """Calculate overall stock score (0-100)"""
    score = 0
    latest = df.iloc[-1]
    
    # RSI Score (0-20 points)
    rsi = latest['RSI']
    if 30 <= rsi <= 70:  # Neutral zone
        score += 20
    elif 40 <= rsi <= 60:  # Sweet spot
        score += 15
    elif rsi < 30:  # Oversold (potential buy)
        score += 18
    else:  # Overbought
        score += 5
    
    # Trend Score (0-25 points)
    if latest['SMA_20'] > latest['SMA_50'] > latest['SMA_200']:
        score += 25  # Strong uptrend
    elif latest['SMA_20'] > latest['SMA_50']:
        score += 20  # Uptrend
    elif latest['SMA_50'] > latest['SMA_200']:
        score += 15  # Medium-term uptrend
    else:
        score += 5
    
    # MACD Score (0-15 points)
    if latest['MACD'] > latest['MACD_Signal'] and latest['MACD_Hist'] > 0:
        score += 15  # Bullish crossover
    elif latest['MACD'] > latest['MACD_Signal']:
        score += 12
    else:
        score += 5
    
    # Volume Score (0-10 points)
    avg_volume = df['Volume'].tail(20).mean()
    if latest['Volume'] > avg_volume * 1.5:
        score += 10  # High volume
    elif latest['Volume'] > avg_volume:
        score += 7
    else:
        score += 4
    
    # Momentum Score (0-15 points)
    momentum_20d = ((latest['Close'] - df['Close'].iloc[-20]) / df['Close'].iloc[-20]) * 100
    if momentum_20d > 10:
        score += 15
    elif momentum_20d > 5:
        score += 12
    elif momentum_20d > 0:
        score += 8
    else:
        score += 3
    
    # ADX Score (0-10 points) - Trend strength
    if latest['ADX'] > 25:
        score += 10  # Strong trend
    elif latest['ADX'] > 20:
        score += 7
    else:
        score += 4
    
    # Volatility Score (0-5 points)
    volatility = (latest['ATR'] / latest['Close']) * 100
    if 1 <= volatility <= 3:  # Optimal volatility
        score += 5
    elif volatility < 5:
        score += 3
    else:
        score += 1
    
    return min(int(score), 100)

def calculate_targets(df):
    """Calculate entry, target, and stop loss"""
    latest_price = df['Close'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    
    # Entry: Current price
    entry_price = round(latest_price, 2)
    
    # Target: 3x ATR above current price (aggressive)
    target_price = round(latest_price + (3 * atr), 2)
    
    # Stop Loss: 2x ATR below current price
    stop_loss = round(latest_price - (2 * atr), 2)
    
    # Estimate target date (based on average momentum)
    momentum = ((df['Close'].iloc[-1] - df['Close'].iloc[-20]) / df['Close'].iloc[-20]) * 100
    if momentum > 10:
        days_to_target = 30
    elif momentum > 5:
        days_to_target = 60
    else:
        days_to_target = 90
    
    target_date = (datetime.now() + timedelta(days=days_to_target)).strftime('%b %d, %Y')
    
    return entry_price, target_price, stop_loss, target_date

def analyze_single_stock(symbol, filters):
    """Analyze a single stock"""
    try:
        # Fetch data
        stock = yf.Ticker(symbol)
        df = stock.history(period='1y')
        
        if df.empty or len(df) < 200:
            return None
        
        info = stock.info
        
        # Apply filters
        current_price = df['Close'].iloc[-1]
        
        if filters.get('minPrice') and current_price < float(filters['minPrice']):
            return None
        if filters.get('maxPrice') and current_price > float(filters['maxPrice']):
            return None
        
        volume = df['Volume'].iloc[-1] / 1_000_000  # in millions
        if filters.get('minVolume') and volume < float(filters['minVolume']):
            return None
        
        market_cap = info.get('marketCap', 0) / 1_000_000_000  # in billions
        if filters.get('minMarketCap') and market_cap < float(filters['minMarketCap']):
            return None
        if filters.get('maxMarketCap') and market_cap > float(filters['maxMarketCap']):
            return None
        
        sector = info.get('sector', '').lower()
        if filters.get('sector') and filters['sector'] != 'all':
            if filters['sector'].lower() not in sector:
                return None
        
        # Calculate indicators
        df = calculate_technical_indicators(df)
        
        if df['RSI'].iloc[-1] == np.nan:
            return None
        
        # Calculate score
        score = calculate_score(df, info)
        
        # Only return stocks with score >= 60
        if score < 60:
            return None
        
        # Calculate targets
        entry_price, target_price, stop_loss, target_date = calculate_targets(df)
        
        # Get latest metrics
        latest = df.iloc[-1]
        
        return {
            'symbol': symbol,
            'name': info.get('longName', symbol),
            'score': score,
            'entryPrice': entry_price,
            'targetPrice': target_price,
            'stopLoss': stop_loss,
            'targetDate': target_date,
            'volume': f"{volume:.1f}M",
            'marketCap': f"{market_cap:.1f}B",
            'rsi': round(latest['RSI'], 2),
            'trend': 'Bullish' if latest['SMA_20'] > latest['SMA_50'] else 'Bearish',
            'peRatio': round(info.get('forwardPE', 0), 2) if info.get('forwardPE') else 'N/A',
            'momentum': round(((latest['Close'] - df['Close'].iloc[-20]) / df['Close'].iloc[-20]) * 100, 2),
            'sector': info.get('sector', 'Unknown')
        }
        
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

@app.route('/api/scan', methods=['POST'])
def scan_stocks():
    """Main endpoint to scan stocks"""
    try:
        filters = request.json or {}
        
        results = []
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(analyze_single_stock, symbol, filters): symbol 
                      for symbol in STOCK_UNIVERSE}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # Sort by score (highest first)
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top 10
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
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'stocksAvailable': len(STOCK_UNIVERSE),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
