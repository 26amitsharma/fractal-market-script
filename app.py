from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os
from datetime import datetime, timedelta

app = Flask(__name__)

api_key = os.environ.get("KITE_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET")

kite = KiteConnect(api_key=api_key)

def compute_xy(samples, interval):
    highs = [c['high'] for c in samples]
    lows = [c['low'] for c in samples]
    closes = [c['close'] for c in samples]

    X = max(highs) - min(lows)
    total_path = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
    straight_line = abs(closes[-1] - closes[0])
    Y = round(total_path - straight_line, 2)
    direction = "up" if closes[-1] > closes[0] else "down"
    degree = round((closes[-1] - closes[0]) / X * 100, 2)
    y_x_ratio = round(Y / X, 2) if X > 0 else 0

    return {
        "interval": interval,
        "samples": len(samples),
        "X": round(X, 2),
        "Y": round(Y, 2),
        "Y_X_ratio": y_x_ratio,
        "direction": direction,
        "degree_pct": degree,
        "start_price": closes[0],
        "end_price": closes[-1]
    }

def fetch_samples(interval, days=10):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = kite.historical_data(
        instrument_token=256265,
        from_date=from_date,
        to_date=to_date,
        interval=interval
    )
    return data[-30:]

@app.route('/')
def home():
    login_url = kite.login_url()
    return jsonify({
        "status": "FMS - Fractal Market Script is live",
        "login_url": login_url
    })

@app.route('/callback')
def callback():
    request_token = request.args.get('request_token')
    if not request_token:
        return jsonify({"error": "No request token received"}), 400
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        return jsonify({
            "status": "authenticated",
            "access_token": access_token
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/candles')
def candles():
    access_token = request.args.get('token')
    interval = request.args.get('interval', '5minute')
    if not access_token:
        return jsonify({"error": "No access token provided"}), 400
    try:
        kite.set_access_token(access_token)
        samples = fetch_samples(interval)
        if len(samples) < 30:
            return jsonify({"error": "Not enough data", "count": len(samples)}), 400
        return jsonify(compute_xy(samples, interval))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/compare')
def compare():
    access_token = request.args.get('token')
    if not access_token:
        return jsonify({"error": "No access token provided"}), 400
    try:
        kite.set_access_token(access_token)

        intervals = [
            ("minute", 5),
            ("5minute", 5),
            ("15minute", 15)
        ]

        results = []
        for interval, days in intervals:
            samples = fetch_samples(interval, days=days)
            if len(samples) >= 30:
                results.append(compute_xy(samples, interval))

        # Signal summary
        directions = [r["direction"] for r in results]
        all_same = len(set(directions)) == 1
        signal = "ALIGNED - all scales agree" if all_same else "DIVERGED - scales disagree"

        parent = results[2] if len(results) > 2 else None
        children = results[:2]
        child_dirs = [c["direction"] for c in children]
        
        pressure = "neutral"
        if parent:
            if all(d != parent["direction"] for d in child_dirs):
                pressure = "HIGH - children challenging parent"
            elif all(d == parent["direction"] for d in child_dirs):
                pressure = "LOW - children confirming parent"
            else:
                pressure = "MEDIUM - mixed child signals"

        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scales": results,
            "signal": signal,
            "transformation_pressure": pressure
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
