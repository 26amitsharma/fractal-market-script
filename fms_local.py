from kiteconnect import KiteConnect
from datetime import datetime, timedelta

api_key = "tsm9w570sr8un8kj"
access_token = "pNFU0k6ESU26b5oHDxzgkiAVG3RZBWQj"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

INSTRUMENTS = {
    "DEFENCE_ETF": 6385665
}

# interval, label, span, interval_mins, days, n_samples, color_theme
GENERATIONS = [
    ("minute",   "G1", "30 mins",   1,    5,   90, "warm"),
    ("15minute", "G2", "7.5 hours", 15,   30,  90, "amber"),
    ("day",      "G3", "6 weeks",   390,  180, 90, "teal"),
    ("week",     "G4", "1.4 years", 1950, 800, 90, "cool"),
]

# Color themes per generation
# Each theme: (low_vol_color, high_vol_color, body_trail_bg)
COLOR_THEMES = {
    "warm":  {"low": (180, 60,  60),  "high": (255, 80,  20),  "bg": "#2a1a1a"},
    "amber": {"low": (180, 140, 40),  "high": (255, 200, 0),   "bg": "#2a2a1a"},
    "teal":  {"low": (40,  140, 140), "high": (0,   220, 200), "bg": "#1a2a2a"},
    "cool":  {"low": (60,  60,  180), "high": (100, 100, 255), "bg": "#1a1a2a"},
}

def fetch_n_samples(instrument_token, interval, n=90, days=30):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = kite.historical_data(
        instrument_token=instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval=interval
    )
    return data[-n:]

def compute_xy(samples, label, interval_minutes=1):
    highs = [c['high'] for c in samples]
    lows = [c['low'] for c in samples]
    closes = [c['close'] for c in samples]
    volumes = [c['volume'] for c in samples]  # raw volume, no normalization

    X = max(highs) - min(lows)
    total_path = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
    straight_line = abs(closes[-1] - closes[0])
    Y = round(total_path - straight_line, 2)
    direction = "up" if closes[-1] > closes[0] else "down"
    degree = round((closes[-1] - closes[0]) / X * 100, 2) if X > 0 else 0
    y_x_ratio = round(Y / X, 2) if X > 0 else 0

    avg_volume = sum(volumes) / len(volumes)
    body_indices = [i for i, v in enumerate(volumes) if v >= avg_volume]
    limb_indices = [i for i, v in enumerate(volumes) if v < avg_volume]

    return {
        "label": label,
        "X": round(X, 2),
        "Y": round(Y, 2),
        "Y_X_ratio": y_x_ratio,
        "direction": direction,
        "degree_pct": degree,
        "start_price": closes[0],
        "end_price": closes[-1],
        "volumes": volumes,
        "avg_volume": round(avg_volume, 2),
        "body_count": len(body_indices),
        "limb_count": len(limb_indices),
        "closes": closes,
        "highs": highs,
        "lows": lows
    }

def get_common_scale(results):
    all_highs = [h for r in results for h in r['highs']]
    all_lows = [l for r in results for l in r['lows']]
    all_vols = [v for r in results for v in r['volumes']]
    return min(all_lows), max(all_highs), min(all_vols), max(all_vols)

def volume_color(v, min_vol, max_vol, theme):
    vol_range = max_vol - min_vol if max_vol != min_vol else 1
    ratio = (v - min_vol) / vol_range
    low = COLOR_THEMES[theme]["low"]
    high = COLOR_THEMES[theme]["high"]
    r = int(low[0] + ratio * (high[0] - low[0]))
    g = int(low[1] + ratio * (high[1] - low[1]))
    b = int(low[2] + ratio * (high[2] - low[2]))
    return f"rgb({r},{g},{b})"

def render_creature(r, theme="warm", svg_width=240, svg_height=150, padding=25,
                    global_min=None, global_max=None,
                    global_max_vol=None, global_min_vol=None):
    volumes = r['volumes']
    closes = r['closes']
    highs = r['highs']
    lows = r['lows']

    price_min = global_min if global_min is not None else min(lows)
    price_max = global_max if global_max is not None else max(highs)
    price_range = price_max - price_min if price_max != price_min else 1
    price_mid = (price_max + price_min) / 2

    max_vol = global_max_vol if global_max_vol is not None else max(volumes)
    min_vol = global_min_vol if global_min_vol is not None else min(volumes)

    min_size = 3
    max_size = 20
    vol_range = max_vol - min_vol if max_vol != min_vol else 1
    sizes = [min_size + (v - min_vol) / vol_range * (max_size - min_size) for v in volumes]

    n = len(closes)
    x_step = (svg_width - 2 * padding) / (n - 1)

    def price_to_y(p):
        return svg_height - padding - ((p - price_min) / price_range) * (svg_height - 2 * padding)

    ref_lines = []
    y_ceil = price_to_y(price_max)
    y_mid = price_to_y(price_mid)
    y_floor = price_to_y(price_min)

    ref_lines.append(f'<line x1="{padding}" y1="{y_ceil:.1f}" x2="{svg_width-padding}" y2="{y_ceil:.1f}" stroke="#444" stroke-width="0.8" stroke-dasharray="3,3"/>')
    ref_lines.append(f'<line x1="{padding}" y1="{y_mid:.1f}" x2="{svg_width-padding}" y2="{y_mid:.1f}" stroke="#555" stroke-width="0.8" stroke-dasharray="3,3"/>')
    ref_lines.append(f'<line x1="{padding}" y1="{y_floor:.1f}" x2="{svg_width-padding}" y2="{y_floor:.1f}" stroke="#444" stroke-width="0.8" stroke-dasharray="3,3"/>')
    ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_ceil:.1f}" fill="#555" font-size="7">{price_max:.1f}</text>')
    ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_mid:.1f}" fill="#555" font-size="7">{price_mid:.1f}</text>')
    ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_floor:.1f}" fill="#555" font-size="7">{price_min:.1f}</text>')

    lines_svg = []
    circles_svg = []

    for i in range(1, n):
        x1 = padding + (i-1) * x_step
        y1 = price_to_y(closes[i-1])
        x2 = padding + i * x_step
        y2 = price_to_y(closes[i])
        lines_svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#333" stroke-width="1"/>')

    for i, (v, c, s) in enumerate(zip(volumes, closes, sizes)):
        cx = padding + i * x_step
        cy = price_to_y(c)
        color = volume_color(v, min_vol, max_vol, theme)
        stroke_w = "2.5" if i == n-1 else "1.5"
        circles_svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s:.1f}" fill="none" stroke="{color}" stroke-width="{stroke_w}"/>')

    arrow = "↑" if r['direction'] == 'up' else "↓"
    title_color = "#4f8" if r['direction'] == 'up' else "#f84"

    return f'''<div style="display:inline-block; margin:4px; vertical-align:top;">
  <div style="color:{title_color}; font-size:10px; margin-bottom:2px;">{arrow} {r["label"]}</div>
  <div style="color:#678; font-size:8px; margin-bottom:3px;">X={r["X"]} Y={r["Y"]} Y/X={r["Y_X_ratio"]} Deg={r["degree_pct"]}%</div>
  <svg width="{svg_width}" height="{svg_height}" style="background:#1a1a1a; border-radius:6px; border:1px solid #2a2a2a">
    {''.join(ref_lines)}
    {''.join(lines_svg)}
    {''.join(circles_svg)}
  </svg>
</div>'''

def render_body_trail(results, gen_label, span_label, theme="warm",
                      svg_width=240, svg_height=150, padding=25,
                      global_min=None, global_max=None,
                      global_max_vol=None, global_min_vol=None):
    all_bodies = []
    for r in results:
        volumes = r['volumes']
        closes = r['closes']
        avg_vol = r['avg_volume']
        indexed = [(i, v, c) for i, (v, c) in enumerate(zip(volumes, closes)) if v >= avg_vol]
        top5 = sorted(indexed, key=lambda x: x[1], reverse=True)[:5]
        top5_time_ordered = sorted(top5, key=lambda x: x[0])
        all_bodies.extend([(v, c) for i, v, c in top5_time_ordered])

    if not all_bodies:
        return ""

    price_min = global_min if global_min is not None else min(c for _, c in all_bodies)
    price_max = global_max if global_max is not None else max(c for _, c in all_bodies)
    price_range = price_max - price_min if price_max != price_min else 1
    price_mid = (price_max + price_min) / 2

    max_vol = global_max_vol if global_max_vol is not None else max(v for v, _ in all_bodies)
    min_vol = global_min_vol if global_min_vol is not None else min(v for v, _ in all_bodies)
    vol_range = max_vol - min_vol if max_vol != min_vol else 1

    n = len(all_bodies)
    x_step = (svg_width - 2 * padding) / (n - 1) if n > 1 else 1

    def price_to_y(p):
        return svg_height - padding - ((p - price_min) / price_range) * (svg_height - 2 * padding)

    ref_lines = []
    y_ceil = price_to_y(price_max)
    y_mid = price_to_y(price_mid)
    y_floor = price_to_y(price_min)

    ref_lines.append(f'<line x1="{padding}" y1="{y_ceil:.1f}" x2="{svg_width-padding}" y2="{y_ceil:.1f}" stroke="#444" stroke-width="0.8" stroke-dasharray="3,3"/>')
    ref_lines.append(f'<line x1="{padding}" y1="{y_mid:.1f}" x2="{svg_width-padding}" y2="{y_mid:.1f}" stroke="#555" stroke-width="0.8" stroke-dasharray="3,3"/>')
    ref_lines.append(f'<line x1="{padding}" y1="{y_floor:.1f}" x2="{svg_width-padding}" y2="{y_floor:.1f}" stroke="#444" stroke-width="0.8" stroke-dasharray="3,3"/>')
    ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_ceil:.1f}" fill="#555" font-size="7">{price_max:.1f}</text>')
    ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_mid:.1f}" fill="#555" font-size="7">{price_mid:.1f}</text>')
    ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_floor:.1f}" fill="#555" font-size="7">{price_min:.1f}</text>')

    lines_svg = []
    circles_svg = []

    points = []
    for i, (v, c) in enumerate(all_bodies):
        cx = padding + i * x_step
        cy = price_to_y(c)
        points.append((cx, cy, v))

    for i in range(1, len(points)):
        x1, y1, _ = points[i-1]
        x2, y2, _ = points[i]
        lines_svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#555" stroke-width="1" stroke-dasharray="2,2"/>')

    for i, (cx, cy, v) in enumerate(points):
        ratio = (v - min_vol) / vol_range if vol_range > 0 else 0
        size = 3 + ratio * 17
        color = volume_color(v, min_vol, max_vol, theme)
        stroke_w = "2.5" if i == len(points)-1 else "1.5"
        circles_svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="none" stroke="{color}" stroke-width="{stroke_w}"/>')

    first_price = all_bodies[0][1]
    last_price = all_bodies[-1][1]
    direction = "up" if last_price > first_price else "down"
    arrow = "↑" if direction == "up" else "↓"
    title_color = "#4f8" if direction == "up" else "#f84"
    bg = COLOR_THEMES[theme]["bg"]

    return f'''<div style="display:inline-block; margin:4px; vertical-align:top;">
  <div style="color:{title_color}; font-size:10px; margin-bottom:2px;">{arrow} {gen_label} Body Trail</div>
  <div style="color:#678; font-size:8px; margin-bottom:3px;">{span_label} — pure conviction path</div>
  <svg width="{svg_width}" height="{svg_height}" style="background:{bg}; border-radius:6px; border:1px solid #3a3a5a">
    {''.join(ref_lines)}
    {''.join(lines_svg)}
    {''.join(circles_svg)}
  </svg>
</div>'''

def generate_visual(instrument_name, token):
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS — {instrument_name}</title>
<style>
  body {{ background: #111; font-family: monospace; color: #eee; padding: 15px; }}
  h2 {{ color: #4af; margin-bottom: 4px; font-size: 16px; }}
  .section {{ margin: 15px 0; }}
  .section-title {{ color: #888; font-size: 11px; margin-bottom: 6px; border-bottom: 1px solid #222; padding-bottom: 3px; }}
</style>
</head>
<body>
<h2>FMS — {instrument_name}</h2>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
'''

    for interval, gen_label, span_label, interval_mins, days, n_samples, theme in GENERATIONS:
        raw = fetch_n_samples(token, interval, n=n_samples, days=days)
        windows = [raw[i*30:(i+1)*30] for i in range(3) if len(raw[i*30:(i+1)*30]) == 30]
        if not windows:
            continue

        results = [compute_xy(w, f"{gen_label}.{i+1} {'(current)' if i==len(windows)-1 else ''}",
                              interval_minutes=interval_mins)
                   for i, w in enumerate(windows)]

        # Per-generation price and volume scale
        g_min, g_max, g_vmin, g_vmax = get_common_scale(results)

        html += f'''<div class="section">
<div class="section-title">{gen_label}: {span_label} — {len(windows)} windows + Body Trail</div>
<div>'''

        for r in results:
            html += render_creature(r, theme=theme,
                                    global_min=g_min, global_max=g_max,
                                    global_min_vol=g_vmin, global_max_vol=g_vmax)

        html += render_body_trail(results, gen_label, span_label, theme=theme,
                                  global_min=g_min, global_max=g_max,
                                  global_min_vol=g_vmin, global_max_vol=g_vmax)

        html += '</div></div>\n'

    html += '</body></html>'
    return html

for name, token in INSTRUMENTS.items():
    html = generate_visual(name, token)
    filename = f"fms_visual_{name.lower()}.html"
    with open(filename, 'w') as f:
        f.write(html)
    print(f"Visual saved: {filename}")

