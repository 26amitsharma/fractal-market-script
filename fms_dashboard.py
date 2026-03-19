from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from collections import defaultdict

api_key = "tsm9w570sr8un8kj"
access_token = "pNFU0k6ESU26b5oHDxzgkiAVG3RZBWQj"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

INSTRUMENT = 6385665  # DEFENCE ETF
INSTRUMENT_NAME = "DEFENCE ETF"

PATTERNS = {
    ("G3", "lower", "<50%"):   {"excess": +18.6, "signal": "BULLISH", "strength": "STRONG",  "note": "6-week support zone — 53.3% bullish historically"},
    ("G3", "upper", "<50%"):   {"excess": -18.0, "signal": "BEARISH", "strength": "STRONG",  "note": "6-week resistance — 50% both-down historically"},
    ("G3", "lower", "50-99%"): {"excess": -34.7, "signal": "BEARISH", "strength": "STRONG",  "note": "Partial support failure — 0% both-up"},
    ("G4", "upper", "100%"):   {"excess": +15.4, "signal": "BULLISH", "strength": "STRONG",  "note": "Multi-year upper absorption — 0% both-down"},
    ("G4", "upper", "<50%"):   {"excess":  -3.8, "signal": "NEUTRAL", "strength": "NOISE",   "note": "Weak signal for Defence ETF"},
    ("G2", "upper", "100%"):   {"excess": -14.0, "signal": "BEARISH", "strength": "MEDIUM",  "note": "7.5hr resistance absorption — bearish lean"},
    ("G2", "upper", "50-99%"): {"excess": -12.3, "signal": "BEARISH", "strength": "MEDIUM",  "note": "7.5hr partial resistance — bearish lean"},
    ("G1", "upper", "50-99%"): {"excess":  -8.8, "signal": "BEARISH", "strength": "MEDIUM",  "note": "30min partial resistance"},
}

GENERATIONS = [
    ("minute",   "G1", "30 mins",   1,    5,   "warm"),
    ("15minute", "G2", "7.5 hours", 15,   30,  "amber"),
    ("day",      "G3", "6 weeks",   390,  180, "teal"),
    ("week",     "G4", "1.4 years", 1950, 800, "cool"),
]

COLOR_THEMES = {
    "warm":  {"low": (180, 60,  60),  "high": (255, 80,  20),  "bg": "#2a1a1a"},
    "amber": {"low": (180, 140, 40),  "high": (255, 200, 0),   "bg": "#2a2a1a"},
    "teal":  {"low": (40,  140, 140), "high": (0,   220, 200), "bg": "#1a2a2a"},
    "cool":  {"low": (60,  60,  180), "high": (100, 100, 255), "bg": "#1a1a2a"},
}

def fetch_n_samples(interval, n=90, days=30):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = kite.historical_data(INSTRUMENT, from_date, to_date, interval)
    return data[-n:]

def compute_xy(samples, label, interval_minutes=1):
    highs = [c['high'] for c in samples]
    lows = [c['low'] for c in samples]
    closes = [c['close'] for c in samples]
    volumes = [c['volume'] for c in samples]

    X = max(highs) - min(lows)
    total_path = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
    straight_line = abs(closes[-1] - closes[0])
    Y = round(total_path - straight_line, 2)
    direction = "up" if closes[-1] > closes[0] else "down"
    degree = round((closes[-1] - closes[0]) / X * 100, 2) if X > 0 else 0
    y_x_ratio = round(Y / X, 2) if X > 0 else 0
    avg_volume = sum(volumes) / len(volumes) if sum(volumes) > 0 else 1

    return {
        "label": label,
        "X": round(X, 2), "Y": round(Y, 2),
        "Y_X_ratio": y_x_ratio, "direction": direction,
        "degree_pct": degree,
        "start_price": closes[0], "end_price": closes[-1],
        "volumes": volumes, "avg_volume": round(avg_volume, 2),
        "closes": closes, "highs": highs, "lows": lows
    }

def get_common_scale(results):
    all_highs = [h for r in results for h in r['highs']]
    all_lows = [l for r in results for l in r['lows']]
    all_vols = [v for r in results for v in r['volumes']]
    return min(all_lows), max(all_highs), min(all_vols), max(all_vols)

def volume_color_str(v, min_vol, max_vol, theme):
    vol_range = max_vol - min_vol if max_vol != min_vol else 1
    ratio = (v - min_vol) / vol_range
    low = COLOR_THEMES[theme]["low"]
    high = COLOR_THEMES[theme]["high"]
    r = int(low[0] + ratio * (high[0] - low[0]))
    g = int(low[1] + ratio * (high[1] - low[1]))
    b = int(low[2] + ratio * (high[2] - low[2]))
    return f"rgb({r},{g},{b})"

def render_creature(r, theme, svg_width=240, svg_height=150, padding=25,
                    global_min=None, global_max=None, global_max_vol=None, global_min_vol=None):
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
    vol_range = max_vol - min_vol if max_vol != min_vol else 1

    min_size, max_size = 3, 20
    sizes = [min_size + (v - min_vol) / vol_range * (max_size - min_size) for v in volumes]

    n = len(closes)
    x_step = (svg_width - 2 * padding) / (n - 1)

    def price_to_y(p):
        return svg_height - padding - ((p - price_min) / price_range) * (svg_height - 2 * padding)

    ref_lines = []
    y_ceil = price_to_y(price_max)
    y_mid = price_to_y(price_mid)
    y_floor = price_to_y(price_min)

    for y_val, label_val in [(y_ceil, price_max), (y_mid, price_mid), (y_floor, price_min)]:
        dash = "3,3"
        col = "#444" if y_val != y_mid else "#555"
        ref_lines.append(f'<line x1="{padding}" y1="{y_val:.1f}" x2="{svg_width-padding}" y2="{y_val:.1f}" stroke="{col}" stroke-width="0.8" stroke-dasharray="{dash}"/>')
        ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_val:.1f}" fill="#444" font-size="7">{label_val:.1f}</text>')

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
        color = volume_color_str(v, min_vol, max_vol, theme)
        sw = "2.5" if i == n-1 else "1.5"
        circles_svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s:.1f}" fill="none" stroke="{color}" stroke-width="{sw}"/>')

    arrow = "↑" if r['direction'] == 'up' else "↓"
    title_color = "#4f8" if r['direction'] == 'up' else "#f84"

    return f'''<div style="display:inline-block; margin:4px; vertical-align:top;">
  <div style="color:{title_color}; font-size:10px; margin-bottom:2px;">{arrow} {r["label"]}</div>
  <div style="color:#678; font-size:8px; margin-bottom:3px;">X={r["X"]} Y={r["Y"]} Y/X={r["Y_X_ratio"]} Deg={r["degree_pct"]}%</div>
  <svg width="{svg_width}" height="{svg_height}" style="background:#1a1a1a; border-radius:6px; border:1px solid #2a2a2a">
    {''.join(ref_lines)}{''.join(lines_svg)}{''.join(circles_svg)}
  </svg>
</div>'''

def render_body_trail(results, gen_label, span_label, theme,
                      svg_width=240, svg_height=150, padding=25,
                      global_min=None, global_max=None, global_max_vol=None, global_min_vol=None):
    all_bodies = []
    for r in results:
        volumes = r['volumes']
        closes = r['closes']
        avg_vol = r['avg_volume']
        indexed = [(i, v, c) for i, (v, c) in enumerate(zip(volumes, closes)) if v >= avg_vol]
        top5 = sorted(indexed, key=lambda x: x[1], reverse=True)[:5]
        top5_ordered = sorted(top5, key=lambda x: x[0])
        all_bodies.extend([(v, c) for i, v, c in top5_ordered])

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
    for y_val, lv in [(price_to_y(price_max), price_max), (price_to_y(price_mid), price_mid), (price_to_y(price_min), price_min)]:
        ref_lines.append(f'<line x1="{padding}" y1="{y_val:.1f}" x2="{svg_width-padding}" y2="{y_val:.1f}" stroke="#444" stroke-width="0.8" stroke-dasharray="3,3"/>')
        ref_lines.append(f'<text x="{svg_width-padding+2}" y="{y_val:.1f}" fill="#444" font-size="7">{lv:.1f}</text>')

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
        color = volume_color_str(v, min_vol, max_vol, theme)
        sw = "2.5" if i == len(points)-1 else "1.5"
        circles_svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="none" stroke="{color}" stroke-width="{sw}"/>')

    first_price = all_bodies[0][1]
    last_price = all_bodies[-1][1]
    direction = "up" if last_price > first_price else "down"
    arrow = "↑" if direction == "up" else "↓"
    title_color = "#4f8" if direction == "up" else "#f84"
    bg = COLOR_THEMES[theme]["bg"]

    return f'''<div style="display:inline-block; margin:4px; vertical-align:top;">
  <div style="color:{title_color}; font-size:10px; margin-bottom:2px;">{arrow} {gen_label} Body Trail</div>
  <div style="color:#678; font-size:8px; margin-bottom:3px;">{span_label} — conviction path</div>
  <svg width="{svg_width}" height="{svg_height}" style="background:{bg}; border-radius:6px; border:1px solid #3a3a5a">
    {''.join(ref_lines)}{''.join(lines_svg)}{''.join(circles_svg)}
  </svg>
</div>'''

def analyze_signal(candles, gen_label):
    if len(candles) < 5:
        return None

    closes = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]
    avg_vol = sum(volumes) / len(volumes) if sum(volumes) > 0 else 1
    max_vol = max(volumes)
    price_min = min(closes)
    price_max = max(closes)
    price_range = price_max - price_min if price_max != price_min else 1
    center = (price_min + price_max) / 2

    X = round(price_max - price_min, 2)
    total_path = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
    straight_line = abs(closes[-1] - closes[0])
    Y = round(total_path - straight_line, 2)
    Y_X = round(Y / X, 2) if X > 0 else 0
    direction = "UP" if closes[-1] > closes[0] else "DOWN"
    degree = round((closes[-1] - closes[0]) / X * 100, 2) if X > 0 else 0

    current_price = closes[-1]
    current_position = "upper" if current_price > center else "lower"

    # Y/X interpretation
    if Y_X > 4:
        yx_note = "⚡ Very high inefficiency — ranging/consolidating"
    elif Y_X > 2:
        yx_note = "↔ Moderate inefficiency — mixed movement"
    elif Y_X < 1:
        yx_note = "🎯 Low inefficiency — clean trend"
    else:
        yx_note = "→ Normal movement"

    # Degree interpretation
    abs_deg = abs(degree)
    if abs_deg > 80:
        deg_note = "⚠️ Extreme move — potential exhaustion"
    elif abs_deg > 50:
        deg_note = "💪 Strong directional conviction"
    elif abs_deg > 20:
        deg_note = "📈 Moderate conviction"
    else:
        deg_note = "😴 Weak conviction — low degree move"

    # Pattern detection
    pattern_counts = defaultdict(int)
    for i in range(1, len(candles) - 2):
        v = volumes[i]
        c = closes[i]
        if v < avg_vol:
            continue

        position = "upper" if c > center else "lower"
        radius = (v / max_vol) * 0.15 * price_range

        nearby_smaller = sum(
            1 for j in range(max(0, i-3), min(len(candles), i+4))
            if j != i and volumes[j] < v and abs(closes[j] - c) <= radius
        )
        total_smaller = sum(
            1 for j in range(max(0, i-3), min(len(candles), i+4))
            if j != i and volumes[j] < v
        )

        pct = nearby_smaller / total_smaller if total_smaller > 0 else 1.0
        tier = "100%" if pct >= 1.0 else "50-99%" if pct >= 0.5 else "<50%"

        key = (gen_label, position, tier)
        if key in PATTERNS and PATTERNS[key]["strength"] != "NOISE":
            pattern_counts[key] += 1

    fired_patterns = []
    for key, count in pattern_counts.items():
        p = PATTERNS[key]
        fired_patterns.append({
            "position": key[1], "tier": key[2],
            "signal": p["signal"], "strength": p["strength"],
            "excess": p["excess"], "note": p["note"], "count": count
        })

    bullish = [p for p in fired_patterns if p["signal"] == "BULLISH"]
    bearish = [p for p in fired_patterns if p["signal"] == "BEARISH"]
    bull_w = sum(p["count"] * (2 if p["strength"] == "STRONG" else 1) for p in bullish)
    bear_w = sum(p["count"] * (2 if p["strength"] == "STRONG" else 1) for p in bearish)

    if not fired_patterns:
        gen_signal, gen_strength, gen_note = "NEUTRAL", "NO PATTERN", "No validated pattern fired"
    elif bullish and bearish:
        gen_signal, gen_strength = "MIXED", "CONFLICTING"
        gen_note = f"Bullish ({bull_w} pts) vs Bearish ({bear_w} pts)"
    elif bullish:
        gen_signal, gen_strength, gen_note = "BULLISH", bullish[0]["strength"], bullish[0]["note"]
    else:
        gen_signal, gen_strength, gen_note = "BEARISH", bearish[0]["strength"], bearish[0]["note"]

    price_zone = f"Price in {'UPPER' if current_position=='upper' else 'LOWER'} half (center {round(center,2)}) — {'resistance' if current_position=='upper' else 'support'} zone"

    return {
        "gen": gen_label, "direction": direction,
        "X": X, "Y": Y, "Y_X": Y_X, "degree": degree,
        "center": round(center, 2), "current_price": round(current_price, 2),
        "current_position": current_position, "price_zone": price_zone,
        "yx_note": yx_note, "deg_note": deg_note,
        "fired_patterns": fired_patterns,
        "bull_weight": bull_w, "bear_weight": bear_w,
        "signal": gen_signal, "strength": gen_strength, "note": gen_note
    }

# Collect all data
all_gen_data = []
signal_results = []

for interval, gen_label, span_label, interval_mins, days, theme in GENERATIONS:
    raw = fetch_n_samples(interval, n=90, days=days)
    windows = [raw[i*30:(i+1)*30] for i in range(3) if len(raw[i*30:(i+1)*30]) == 30]
    if not windows:
        continue

    results = [compute_xy(w, f"{gen_label}.{i+1} {'(current)' if i==len(windows)-1 else ''}",
                          interval_minutes=interval_mins) for i, w in enumerate(windows)]

    g_min, g_max, g_vmin, g_vmax = get_common_scale(results)
    all_gen_data.append((gen_label, span_label, theme, results, g_min, g_max, g_vmin, g_vmax))

    # Signal analysis on current window
    current_candles = fetch_n_samples(interval, n=30, days=days)
    sig = analyze_signal(current_candles, gen_label)
    if sig:
        sig["span"] = span_label
        signal_results.append(sig)

# Master signal
weights = {"G4": 0.40, "G3": 0.28, "G2": 0.20, "G1": 0.12}
bull_score = bear_score = 0
for r in signal_results:
    w = weights.get(r["gen"], 0)
    if r["signal"] == "BULLISH": bull_score += w
    elif r["signal"] == "BEARISH": bear_score += w
    elif r["signal"] == "MIXED":
        total_w = r["bull_weight"] + r["bear_weight"]
        if total_w > 0:
            bull_score += w * (r["bull_weight"] / total_w)
            bear_score += w * (r["bear_weight"] / total_w)

bull_score = round(bull_score, 3)
bear_score = round(bear_score, 3)
total_score = bull_score + bear_score

if bull_score > bear_score + 0.15: master_signal, master_color = "BULLISH", "#4f8"
elif bear_score > bull_score + 0.15: master_signal, master_color = "BEARISH", "#f84"
elif bull_score > bear_score: master_signal, master_color = "LEANING BULLISH", "#af8"
elif bear_score > bull_score: master_signal, master_color = "LEANING BEARISH", "#fa8"
else: master_signal, master_color = "NEUTRAL", "#888"

master_confidence = round(max(bull_score, bear_score) / total_score * 100, 1) if total_score > 0 else 0

# Human readable master summary
all_in_lower = all(r["current_position"] == "lower" for r in signal_results)
g4_neutral = next((r for r in signal_results if r["gen"] == "G4"), None)
high_yx = [r for r in signal_results if r["Y_X"] > 4]
extreme_deg = [r for r in signal_results if abs(r["degree"]) > 80]

summary_lines = []
if all_in_lower:
    summary_lines.append("Price across all timeframes in support zone.")
if g4_neutral and g4_neutral["signal"] == "NEUTRAL":
    summary_lines.append("G4 macro parent silent — no strong multi-year conviction yet.")
if high_yx:
    summary_lines.append(f"{', '.join(r['gen'] for r in high_yx)} showing high inefficiency — market ranging/consolidating.")
if extreme_deg:
    for r in extreme_deg:
        summary_lines.append(f"{r['gen']} extreme {'up' if r['degree']>0 else 'down'} move ({r['degree']}°) — potential exhaustion.")

master_summary = " ".join(summary_lines) if summary_lines else "Mixed signals across timeframes."

def signal_color(s):
    return {"BULLISH":"#4f8","BEARISH":"#f84","MIXED":"#fa8","LEANING BULLISH":"#af8","LEANING BEARISH":"#fa8"}.get(s,"#888")

def strength_color(s):
    return {"STRONG":"#4f8","MEDIUM":"#fa8","CONFLICTING":"#f8a"}.get(s,"#888")

# Build HTML
html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Dashboard — {INSTRUMENT_NAME}</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; }}
  .master {{ background:#1a1a1a; border:1px solid #333; border-radius:8px; padding:20px; margin-bottom:20px; }}
  .gen-block {{ margin:15px 0; }}
  .gen-signal {{ background:#161616; border:1px solid #222; border-radius:6px; padding:12px; margin-top:6px; }}
  .pattern-item {{ background:#1e1e1e; border-left:3px solid #333; padding:5px 10px; margin:3px 0; font-size:11px; border-radius:3px; }}
  .price-zone {{ background:#1a1a2a; border:1px solid #2a2a3a; padding:5px 10px; margin:5px 0; font-size:11px; border-radius:3px; color:#8af; }}
  .yx-note {{ color:#888; font-size:10px; margin:3px 0; }}
  .section-title {{ color:#555; font-size:11px; margin-bottom:6px; border-bottom:1px solid #1a1a1a; padding-bottom:3px; }}
  h2 {{ color:#4af; margin:0 0 4px 0; }}
</style>
</head>
<body>

<div class="master">
  <h2>FMS — {INSTRUMENT_NAME}</h2>
  <div style="color:#555; font-size:10px; margin-bottom:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
  <div style="font-size:30px; color:{master_color}; font-weight:bold; margin:8px 0;">{master_signal}</div>
  <div style="color:#666; font-size:11px; margin-bottom:8px;">Bull: {bull_score} | Bear: {bear_score} | Confidence: {master_confidence}%</div>
  <div style="color:#888; font-size:12px; margin:10px 0; line-height:1.6;">{master_summary}</div>
  <div style="font-size:11px; color:#555; margin-top:8px;">
    {("✅ " + ", ".join(r["gen"] for r in signal_results if r["signal"]=="BULLISH")) if any(r["signal"]=="BULLISH" for r in signal_results) else ""}
    {("⚠️ Mixed: " + ", ".join(r["gen"] for r in signal_results if r["signal"]=="MIXED")) if any(r["signal"]=="MIXED" for r in signal_results) else ""}
    {("🔴 " + ", ".join(r["gen"] for r in signal_results if r["signal"]=="BEARISH")) if any(r["signal"]=="BEARISH" for r in signal_results) else ""}
    {("⬜ " + ", ".join(r["gen"] for r in signal_results if r["signal"]=="NEUTRAL")) if any(r["signal"]=="NEUTRAL" for r in signal_results) else ""}
  </div>
</div>

'''

# Per generation: graphs + signal summary
for gen_label, span_label, theme, results, g_min, g_max, g_vmin, g_vmax in all_gen_data:
    sig = next((r for r in signal_results if r["gen"] == gen_label), None)
    sig_color = signal_color(sig["signal"]) if sig else "#888"

    html += f'<div class="gen-block">\n'
    html += f'<div class="section-title">{gen_label}: {span_label}</div>\n'
    html += '<div>\n'

    for r in results:
        html += render_creature(r, theme, global_min=g_min, global_max=g_max,
                                global_min_vol=g_vmin, global_max_vol=g_vmax)
    html += render_body_trail(results, gen_label, span_label, theme,
                              global_min=g_min, global_max=g_max,
                              global_min_vol=g_vmin, global_max_vol=g_vmax)

    html += '</div>\n'

    if sig:
        dir_arrow = "↑" if sig["direction"] == "UP" else "↓"
        html += f'''<div class="gen-signal">
  <div style="display:flex; justify-content:space-between;">
    <span style="color:#aaa; font-size:12px;">{gen_label} Signal</span>
    <span style="color:{sig_color}; font-weight:bold;">{sig["signal"]} <span style="color:{strength_color(sig["strength"])}; font-size:10px;">{sig["strength"]}</span></span>
  </div>
  <div style="color:#555; font-size:11px; margin:4px 0;">
    {dir_arrow} {sig["direction"]} {sig["degree"]}° | X={sig["X"]} Y={sig["Y"]} Y/X={sig["Y_X"]}
  </div>
  <div class="yx-note">{sig["yx_note"]} | {sig["deg_note"]}</div>
  <div class="price-zone">{sig["price_zone"]}</div>
  <div style="color:#555; font-size:11px; margin:4px 0;">{sig["note"]}</div>
'''
        if sig["fired_patterns"]:
            for p in sig["fired_patterns"]:
                exc_str = f'+{p["excess"]}%' if p["excess"] >= 0 else f'{p["excess"]}%'
                cnt = f'×{p["count"]}' if p["count"] > 1 else ""
                html += f'  <div class="pattern-item" style="border-color:{signal_color(p["signal"])}">{p["signal"]} {cnt} | {p["position"]} half | consumption {p["tier"]} | excess {exc_str} | {p["strength"]} | {p["note"]}</div>\n'

        html += '</div>\n'

    html += '</div>\n'

html += '</body></html>'

with open('fms_dashboard.html', 'w') as f:
    f.write(html)

print(f"Dashboard saved: fms_dashboard.html")
print(f"\nMASTER: {master_signal} | Confidence: {master_confidence}%")
print(f"Bull: {bull_score} | Bear: {bear_score}")
print(f"\nSummary: {master_summary}")
print()
for r in reversed(signal_results):
    print(f"{r['gen']} ({r['span']}): {r['signal']} — {r['strength']}")
    print(f"  {r['yx_note']} | {r['deg_note']}")
    print(f"  {r['price_zone']}")

