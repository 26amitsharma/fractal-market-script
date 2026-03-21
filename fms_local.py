from kiteconnect import KiteConnect
from datetime import datetime, timedelta

api_key = "tsm9w570sr8un8kj"
access_token = "Ika9gOlRs1KUm3bnJhEEKUVjCr4Fqcc7"

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


def generate_merged_flow(all_gen_data):
    # Flow: G4 current | G3 body | G2 body | G1 body | G1 current
    # all_gen_data is ordered G1, G2, G3, G4

    if len(all_gen_data) < 3:
        return ""

    g1_label, g1_span, g1_theme, g1_results, g1_min, g1_max, g1_vmin, g1_vmax = all_gen_data[0]
    g2_label, g2_span, g2_theme, g2_results, g2_min, g2_max, g2_vmin, g2_vmax = all_gen_data[1]
    g3_label, g3_span, g3_theme, g3_results, g3_min, g3_max, g3_vmin, g3_vmax = all_gen_data[2]

    if len(all_gen_data) >= 4:
        g4_label, g4_span, g4_theme, g4_results, g4_min, g4_max, g4_vmin, g4_vmax = all_gen_data[3]
    else:
        g4_results = None

    def get_body_trail(results, vmin, vmax):
        bodies = []
        for r in results:
            volumes = r["volumes"]
            closes = r["closes"]
            avg_vol = r["avg_volume"]
            indexed = [(i, v, c) for i, (v, c) in enumerate(zip(volumes, closes)) if v >= avg_vol]
            top5 = sorted(indexed, key=lambda x: x[1], reverse=True)[:5]
            top5_ordered = sorted(top5, key=lambda x: x[0])
            bodies.extend([(v, c) for i, v, c in top5_ordered])
        return bodies

    def get_current_window(results):
        r = results[-1]
        return list(zip(r["volumes"], r["closes"]))

    # Build 5 panels
    panels = []

    # G4 current
    if g4_results:
        panels.append(("G4 current", g4_theme, get_current_window(g4_results), g4_vmin, g4_vmax))

    # G3 body trail
    panels.append(("G3 body trail", g3_theme, get_body_trail(g3_results, g3_vmin, g3_vmax), g3_vmin, g3_vmax))

    # G2 body trail
    panels.append(("G2 body trail", g2_theme, get_body_trail(g2_results, g2_vmin, g2_vmax), g2_vmin, g2_vmax))

    # G1 body trail
    panels.append(("G1 body trail", g1_theme, get_body_trail(g1_results, g1_vmin, g1_vmax), g1_vmin, g1_vmax))

    # G1 current
    panels.append(("G1 current", g1_theme, get_current_window(g1_results), g1_vmin, g1_vmax))

    n_panels = len(panels)
    svg_width = 1300
    svg_height = 220
    padding = 35
    segment_width = (svg_width - 2 * padding) / n_panels

    svg_elements = []
    seg_last = {}
    seg_first = {}

    for seg_idx, (panel_label, theme, data_points, vmin, vmax) in enumerate(panels):
        if not data_points:
            continue

        seg_start_x = padding + seg_idx * segment_width

        # Per-segment price scale
        closes = [c for v, c in data_points]
        seg_price_min = min(closes)
        seg_price_max = max(closes)
        seg_price_mid = (seg_price_min + seg_price_max) / 2
        seg_price_range = seg_price_max - seg_price_min if seg_price_max != seg_price_min else 1

        def price_to_y(p, pmin=seg_price_min, prange=seg_price_range):
            return svg_height - padding - ((p - pmin) / prange) * (svg_height - 2 * padding)

        # Divider
        if seg_idx > 0:
            svg_elements.append(f'<line x1="{seg_start_x:.1f}" y1="{padding/2}" x2="{seg_start_x:.1f}" y2="{svg_height-padding/2}" stroke="#2a2a2a" stroke-width="1"/>')

        # Label
        label_color = "#aaa" if "current" in panel_label else "#666"
        svg_elements.append(f'<text x="{seg_start_x + segment_width/2:.1f}" y="{padding-12}" fill="{label_color}" font-size="9" text-anchor="middle">{panel_label}</text>')

        # Reference lines
        y_ceil = price_to_y(seg_price_max)
        y_mid = price_to_y(seg_price_mid)
        y_floor = price_to_y(seg_price_min)

        svg_elements.append(f'<line x1="{seg_start_x+5:.1f}" y1="{y_ceil:.1f}" x2="{seg_start_x+segment_width-5:.1f}" y2="{y_ceil:.1f}" stroke="#222" stroke-width="0.8" stroke-dasharray="3,3"/>')
        svg_elements.append(f'<line x1="{seg_start_x+5:.1f}" y1="{y_mid:.1f}" x2="{seg_start_x+segment_width-5:.1f}" y2="{y_mid:.1f}" stroke="#2a2a2a" stroke-width="0.8" stroke-dasharray="3,3"/>')
        svg_elements.append(f'<line x1="{seg_start_x+5:.1f}" y1="{y_floor:.1f}" x2="{seg_start_x+segment_width-5:.1f}" y2="{y_floor:.1f}" stroke="#222" stroke-width="0.8" stroke-dasharray="3,3"/>')

        svg_elements.append(f'<text x="{seg_start_x+7}" y="{y_ceil-2:.1f}" fill="#2a2a2a" font-size="7">{seg_price_max:.1f}</text>')
        svg_elements.append(f'<text x="{seg_start_x+7}" y="{y_floor+8:.1f}" fill="#2a2a2a" font-size="7">{seg_price_min:.1f}</text>')

        # Volume scale
        vol_range = vmax - vmin if vmax != vmin else 1
        n = len(data_points)
        x_step = (segment_width - 20) / (n - 1) if n > 1 else 1

        points = []
        for i, (v, c) in enumerate(data_points):
            cx = seg_start_x + 10 + i * x_step
            cy = price_to_y(c)
            ratio = (v - vmin) / vol_range if vol_range > 0 else 0
            size = 3 + ratio * 14
            low = COLOR_THEMES[theme]["low"]
            high = COLOR_THEMES[theme]["high"]
            r_val = int(low[0] + ratio * (high[0] - low[0]))
            g_val = int(low[1] + ratio * (high[1] - low[1]))
            b_val = int(low[2] + ratio * (high[2] - low[2]))
            color = f"rgb({r_val},{g_val},{b_val})"
            points.append((cx, cy, size, color))

        # Lines
        for i in range(1, len(points)):
            x1, y1, _, _ = points[i-1]
            x2, y2, _, _ = points[i]
            svg_elements.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#333" stroke-width="1"/>')

        # Circles
        for i, (cx, cy, size, color) in enumerate(points):
            sw = "2.5" if i == len(points)-1 else "1.5"
            svg_elements.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="none" stroke="{color}" stroke-width="{sw}"/>')

        if points:
            seg_first[seg_idx] = points[0][:2]
            seg_last[seg_idx] = points[-1][:2]

    # Cross-generation connectors
    for seg_idx in range(n_panels - 1):
        if seg_idx in seg_last and seg_idx + 1 in seg_first:
            x1, y1 = seg_last[seg_idx]
            x2, y2 = seg_first[seg_idx + 1]
            svg_elements.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#444" stroke-width="1" stroke-dasharray="3,3"/>')

    return f"""<div style="margin:0 0 20px 0;">
  <div style="color:#aaa; font-size:12px; margin-bottom:6px; border-bottom:1px solid #222; padding-bottom:4px;">
    &#8592; ZOOM-IN FLOW: G4 current &rarr; G3 body &rarr; G2 body &rarr; G1 body &rarr; G1 current &#8594;
  </div>
  <svg width="{svg_width}" height="{svg_height}" style="background:#151515; border-radius:8px; border:1px solid #2a2a2a">
    {"".join(svg_elements)}
  </svg>
</div>"""


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

    all_gen_data = []

    for interval, gen_label, span_label, interval_mins, days, n_samples, theme in GENERATIONS:
        raw = fetch_n_samples(token, interval, n=n_samples, days=days)
        windows = [raw[i*30:(i+1)*30] for i in range(3) if len(raw[i*30:(i+1)*30]) == 30]
        if not windows:
            continue

        results = [compute_xy(w, f"{gen_label}.{i+1} {'(current)' if i==len(windows)-1 else ''}",
                              interval_minutes=interval_mins)
                   for i, w in enumerate(windows)]

        g_min, g_max, g_vmin, g_vmax = get_common_scale(results)
        all_gen_data.append((gen_label, span_label, theme, results, g_min, g_max, g_vmin, g_vmax))

    # Add merged flow at top
    html += generate_merged_flow(all_gen_data)

    for gen_label, span_label, theme, results, g_min, g_max, g_vmin, g_vmax in all_gen_data:
        html += f'''<div class="section">
<div class="section-title">{gen_label}: {span_label} — {len(results)} windows + Body Trail</div>
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

