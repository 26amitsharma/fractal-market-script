from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os
from datetime import datetime, timedelta

app = Flask(__name__)

api_key = os.environ.get("KITE_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET")

kite = KiteConnect(api_key=api_key)

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
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5)
        data = kite.historical_data(
            instrument_token=256265,
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )
        # Take last 30 samples
        samples = data[-30:]
        if len(samples) < 30:
            return jsonify({"error": "Not enough data", "count": len(samples)}), 400

        # Compute X and Y primitives
        highs = [c['high'] for c in samples]
        lows = [c['low'] for c in samples]
        closes = [c['close'] for c in samples]

        X = max(highs) - min(lows)  # max distance amplitude

        # Y = extra steps: sum of absolute moves vs straight line distance
        total_path = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
        straight_line = abs(closes[-1] - closes[0])
        Y = round(total_path - straight_line, 2)

        direction = "up" if closes[-1] > closes[0] else "down"
        degree = round((closes[-1] - closes[0]) / X * 100, 2)

        return jsonify({
            "interval": interval,
            "samples": len(samples),
            "X": round(X, 2),
            "Y": round(Y, 2),
            "direction": direction,
            "degree_pct": degree,
            "start_price": closes[0],
            "end_price": closes[-1]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
