from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os
from datetime import datetime, timedelta

app = Flask(__name__)

api_key = os.environ.get("KITE_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET")

kite = KiteConnect(api_key=api_key)

# Strict 1:30 generations — each scale is exactly 30 samples of the named interval
INTERVALS = [
    ("minute",   "1min×30",   2),    # ~30 min of market time
    ("30minute", "30min×30",  20),   # ~15 trading days
    ("day",      "1day×30",   50),   # ~2 calendar months
]


def classify_candles(samples):
    """Classify each candle as body (≥ avg vol) or limb (< avg vol).
    Position tracks where in the 30-sample walk the candle falls:
      early  = index 0–9
      middle = index 10–19
      late   = index 20–29
    """
    volumes = [c["volume"] for c in samples]
    avg_vol = sum(volumes) / len(volumes)
    n = len(samples)

    classified = []
    for i, c in enumerate(samples):
        vol = c["volume"]
        kind = "body" if vol >= avg_vol else "limb"

        if i < n / 3:
            position = "early"
        elif i < 2 * n / 3:
            position = "middle"
        else:
            position = "late"

        classified.append({
            "index": i,
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": vol,
            "type": kind,
            "position": position,
            "timestamp": str(c["date"]),
        })

    return classified, avg_vol


def compute_xy(samples, interval, label):
    highs = [c["high"] for c in samples]
    lows = [c["low"] for c in samples]
    closes = [c["close"] for c in samples]

    X = max(highs) - min(lows)
    total_path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    straight_line = abs(closes[-1] - closes[0])
    Y = round(total_path - straight_line, 2)
    direction = "up" if closes[-1] > closes[0] else "down"
    degree = round((closes[-1] - closes[0]) / X * 100, 2) if X > 0 else 0
    y_x_ratio = round(Y / X, 2) if X > 0 else 0

    classified, avg_vol = classify_candles(samples)

    bodies = [c for c in classified if c["type"] == "body"]
    limbs = [c for c in classified if c["type"] == "limb"]

    body_positions = {
        pos: sum(1 for b in bodies if b["position"] == pos)
        for pos in ("early", "middle", "late")
    }

    return {
        "interval": interval,
        "label": label,
        "samples": len(samples),
        "X": round(X, 2),
        "Y": round(Y, 2),
        "Y_X_ratio": y_x_ratio,
        "direction": direction,
        "degree_pct": degree,
        "start_price": closes[0],
        "end_price": closes[-1],
        "avg_volume": round(avg_vol, 2),
        "body_count": len(bodies),
        "limb_count": len(limbs),
        "body_positions": body_positions,
        "candles": classified,
    }


def fetch_samples(interval, days=10):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = kite.historical_data(
        instrument_token=256265,
        from_date=from_date,
        to_date=to_date,
        interval=interval,
    )
    return data[-30:]


# ---------------------------------------------------------------------------
# HTML visual generator
# ---------------------------------------------------------------------------

def _candle_color(candle, max_vol):
    ratio = candle["volume"] / max_vol if max_vol else 0
    if candle["type"] == "body":
        # Warm: orange (low body vol) → red (high body vol)
        r = 255
        g = int(165 * (1 - ratio))
        b = 0
    else:
        # Cool: sky-blue (low limb vol) → teal (high limb vol)
        r = 0
        g = int(160 + 55 * ratio)
        b = int(220 - 40 * ratio)
    return f"rgb({r},{g},{b})"


def generate_html(all_results, filename="fms_visual.html"):
    """Build an SVG visual for each scale:
    - Circles connected by lines
    - Circle radius ∝ volume
    - Warm (orange→red)  = body candle (≥ avg vol)
    - Cool (blue→teal)   = limb candle (< avg vol)
    - Y position         = close price (higher price → higher on canvas)
    """
    W, H, PAD = 920, 420, 60
    MIN_R, MAX_R = 5, 28

    sections = []
    for result in all_results:
        candles = result["candles"]
        label = result["label"]
        n = len(candles)

        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]

        min_p, max_p = min(closes), max(closes)
        price_range = max_p - min_p or 1
        max_vol = max(volumes) or 1

        x_step = (W - 2 * PAD) / (n - 1) if n > 1 else 0

        def to_x(i):
            return PAD + i * x_step

        def to_y(price):
            return PAD + (1 - (price - min_p) / price_range) * (H - 2 * PAD)

        def to_r(vol):
            return MIN_R + (vol / max_vol) * (MAX_R - MIN_R)

        # Connecting lines
        lines = []
        for i in range(1, n):
            x1, y1 = to_x(i - 1), to_y(candles[i - 1]["close"])
            x2, y2 = to_x(i), to_y(candles[i]["close"])
            lines.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
                f'x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#444" stroke-width="1.5" stroke-linecap="round"/>'
            )

        # Circles
        circles = []
        for i, c in enumerate(candles):
            cx, cy = to_x(i), to_y(c["close"])
            r = to_r(c["volume"])
            color = _candle_color(c, max_vol)
            tip = (
                f"#{i + 1} {c['timestamp'][:16]}\n"
                f"Close: {c['close']}\n"
                f"Volume: {c['volume']:,}\n"
                f"Type: {c['type']} / {c['position']}"
            )
            circles.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'fill="{color}" stroke="rgba(255,255,255,0.3)" stroke-width="1.2">'
                f'<title>{tip}</title></circle>'
            )

        # Grid + price axis
        grid = []
        for tick in range(5):
            price = min_p + tick * price_range / 4
            y = to_y(price)
            grid.append(
                f'<line x1="{PAD}" y1="{y:.1f}" x2="{W - PAD}" y2="{y:.1f}" '
                f'stroke="#2a2a3e" stroke-width="1"/>'
                f'<text x="{PAD - 6}" y="{y + 4:.1f}" text-anchor="end" '
                f'font-size="11" fill="#666">{price:.0f}</text>'
            )

        # X-axis index labels (every 5)
        x_labels = []
        for i in range(0, n, 5):
            x = to_x(i)
            x_labels.append(
                f'<text x="{x:.1f}" y="{H - PAD + 18}" text-anchor="middle" '
                f'font-size="11" fill="#555">{i + 1}</text>'
            )

        bp = result["body_positions"]
        dir_color = "#ff7043" if result["direction"] == "up" else "#4dd0e1"

        section = f"""
<div class="scale-block">
  <h2 class="scale-title">{label}</h2>
  <div class="meta">
    Direction: <span style="color:{dir_color}">{result['direction'].upper()}</span>
    &nbsp;|&nbsp; X: {result['X']}
    &nbsp;|&nbsp; Y: {result['Y']}
    &nbsp;|&nbsp; Y/X: {result['Y_X_ratio']}
    &nbsp;|&nbsp; Bodies: {result['body_count']}
      (early&nbsp;{bp['early']}&nbsp;mid&nbsp;{bp['middle']}&nbsp;late&nbsp;{bp['late']})
    &nbsp;|&nbsp; Limbs: {result['limb_count']}
    &nbsp;|&nbsp; Avg vol: {result['avg_volume']:,.0f}
  </div>
  <svg width="{W}" height="{H}" class="chart">
    {''.join(grid)}
    {''.join(x_labels)}
    <text x="{PAD}" y="{H - 8}" font-size="10" fill="#333" font-family="monospace">candle index →</text>
    {''.join(lines)}
    {''.join(circles)}
  </svg>
  <div class="legend">
    <span class="dot warm"></span> body (≥ avg vol) — warm
    &nbsp;&nbsp;
    <span class="dot cool"></span> limb (&lt; avg vol) — cool
    &nbsp;&nbsp; circle size ∝ volume
  </div>
</div>"""
        sections.append(section)

    directions = [r["direction"] for r in all_results]
    all_same = len(set(directions)) == 1
    signal = "ALIGNED" if all_same else "DIVERGED"
    signal_color = "#4dd0e1" if all_same else "#ff7043"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>FMS Visual — {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0b0b16;
    color: #ddd;
    font-family: 'Courier New', monospace;
    padding: 32px;
  }}
  h1 {{
    font-size: 22px;
    color: #fff;
    border-bottom: 1px solid #222;
    padding-bottom: 12px;
    margin-bottom: 6px;
  }}
  .subtitle {{ color: #555; font-size: 13px; margin-bottom: 20px; }}
  .signal-badge {{
    display: inline-block;
    padding: 6px 18px;
    border-radius: 4px;
    background: #111;
    color: {signal_color};
    font-size: 16px;
    border: 1px solid {signal_color}44;
    margin-bottom: 32px;
  }}
  .scale-block {{ margin-bottom: 48px; }}
  .scale-title {{
    font-size: 17px;
    color: #ccc;
    margin-bottom: 6px;
  }}
  .meta {{
    font-size: 12px;
    color: #888;
    margin-bottom: 10px;
    line-height: 1.6;
  }}
  .chart {{
    background: #12121f;
    border-radius: 8px;
    display: block;
    border: 1px solid #1e1e30;
  }}
  .legend {{
    font-size: 11px;
    color: #555;
    margin-top: 8px;
  }}
  .dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    vertical-align: middle;
  }}
  .dot.warm {{ background: #ff7043; }}
  .dot.cool {{ background: #4dd0e1; }}
</style>
</head>
<body>
<h1>Fractal Market Script — 1:30 Visual</h1>
<div class="subtitle">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div class="signal-badge">Signal: {signal}</div>
{''.join(sections)}
</body>
</html>"""

    with open(filename, "w") as f:
        f.write(html)
    return filename


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return jsonify({
        "status": "FMS Local is live",
        "login_url": kite.login_url(),
        "intervals": [label for _, label, _ in INTERVALS],
    })


@app.route("/callback")
def callback():
    request_token = request.args.get("request_token")
    if not request_token:
        return jsonify({"error": "No request token received"}), 400
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        return jsonify({"status": "authenticated", "access_token": access_token})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/compare")
def compare():
    access_token = request.args.get("token")
    if not access_token:
        return jsonify({"error": "No access token provided"}), 400
    try:
        kite.set_access_token(access_token)

        results = []
        for interval, label, days in INTERVALS:
            samples = fetch_samples(interval, days=days)
            if len(samples) >= 30:
                results.append(compute_xy(samples, interval, label))

        directions = [r["direction"] for r in results]
        all_same = len(set(directions)) == 1
        signal = "ALIGNED - all scales agree" if all_same else "DIVERGED - scales disagree"

        if len(results) >= 2:
            parent = results[-1]
            child_dirs = [r["direction"] for r in results[:-1]]
            all_against = all(d != parent["direction"] for d in child_dirs)
            all_confirm = all(d == parent["direction"] for d in child_dirs)
            if all_against:
                pressure = "HIGH - all children challenging parent"
            elif all_confirm:
                pressure = "LOW - all children confirming parent"
            else:
                confirming = sum(1 for d in child_dirs if d == parent["direction"])
                pressure = f"MEDIUM - {confirming} of {len(child_dirs)} children confirming parent"
        else:
            pressure = "insufficient data"

        yx_trend = (
            "increasing"
            if results[-1]["Y_X_ratio"] > results[0]["Y_X_ratio"]
            else "decreasing"
        )

        html_file = generate_html(results)

        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scales": results,
            "signal": signal,
            "transformation_pressure": pressure,
            "inefficiency_trend": yx_trend,
            "visual": html_file,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
