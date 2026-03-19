from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from collections import defaultdict

api_key = "tsm9w570sr8un8kj"
access_token = "pNFU0k6ESU26b5oHDxzgkiAVG3RZBWQj"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

INSTRUMENT = 6385665  # DEFENCE ETF

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
    ("minute",   "G1", "30 mins",   1,    5),
    ("15minute", "G2", "7.5 hours", 15,   30),
    ("day",      "G3", "6 weeks",   390,  180),
    ("week",     "G4", "1.4 years", 1950, 800),
]

def fetch_samples(interval, days, n=30):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = kite.historical_data(INSTRUMENT, from_date, to_date, interval)
    return data[-n:]

def analyze_current_window(candles, gen_label):
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

    # Current price position — separate from historical patterns
    current_price = closes[-1]
    current_position = "upper" if current_price > center else "lower"

    # Find large circles and deduplicate patterns
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
        if pct >= 1.0:
            tier = "100%"
        elif pct >= 0.5:
            tier = "50-99%"
        else:
            tier = "<50%"

        key = (gen_label, position, tier)
        if key in PATTERNS and PATTERNS[key]["strength"] != "NOISE":
            pattern_counts[key] += 1

    # Build deduplicated fired patterns
    fired_patterns = []
    for key, count in pattern_counts.items():
        p = PATTERNS[key]
        fired_patterns.append({
            "position": key[1],
            "tier": key[2],
            "signal": p["signal"],
            "strength": p["strength"],
            "excess": p["excess"],
            "note": p["note"],
            "count": count
        })

    # Determine generation signal — handle MIXED properly
    bullish = [p for p in fired_patterns if p["signal"] == "BULLISH"]
    bearish = [p for p in fired_patterns if p["signal"] == "BEARISH"]

    bull_weight = sum(p["count"] * (2 if p["strength"] == "STRONG" else 1) for p in bullish)
    bear_weight = sum(p["count"] * (2 if p["strength"] == "STRONG" else 1) for p in bearish)

    if not fired_patterns:
        gen_signal = "NEUTRAL"
        gen_strength = "NO PATTERN"
        gen_note = "No validated pattern fired in this window"
    elif bullish and bearish:
        gen_signal = "MIXED"
        gen_strength = "CONFLICTING"
        gen_note = f"Both bullish ({bull_weight} pts) and bearish ({bear_weight} pts) patterns present"
    elif bullish:
        gen_signal = "BULLISH"
        gen_strength = bullish[0]["strength"]
        gen_note = bullish[0]["note"]
    else:
        gen_signal = "BEARISH"
        gen_strength = bearish[0]["strength"]
        gen_note = bearish[0]["note"]

    # Current price zone intelligence — separate layer
    if current_position == "lower":
        price_zone = f"Price in LOWER half (below center {round(center,2)}) — historically support zone"
    else:
        price_zone = f"Price in UPPER half (above center {round(center,2)}) — historically resistance zone"

    return {
        "gen": gen_label,
        "direction": direction,
        "X": X, "Y": Y, "Y_X": Y_X, "degree": degree,
        "center": round(center, 2),
        "current_price": round(current_price, 2),
        "current_position": current_position,
        "price_zone": price_zone,
        "fired_patterns": fired_patterns,
        "bull_weight": bull_weight,
        "bear_weight": bear_weight,
        "signal": gen_signal,
        "strength": gen_strength,
        "note": gen_note
    }

# Analyze all generations
results = []
for interval, gen_label, span_label, interval_mins, days in GENERATIONS:
    candles = fetch_samples(interval, days)
    analysis = analyze_current_window(candles, gen_label)
    if analysis:
        analysis["span"] = span_label
        results.append(analysis)

# Master summary with MIXED handling
weights = {"G4": 0.40, "G3": 0.28, "G2": 0.20, "G1": 0.12}
bull_score = 0
bear_score = 0

for r in results:
    w = weights.get(r["gen"], 0)
    if r["signal"] == "BULLISH":
        bull_score += w
    elif r["signal"] == "BEARISH":
        bear_score += w
    elif r["signal"] == "MIXED":
        # Split weight based on bull/bear weight within generation
        total_w = r["bull_weight"] + r["bear_weight"]
        if total_w > 0:
            bull_score += w * (r["bull_weight"] / total_w)
            bear_score += w * (r["bear_weight"] / total_w)

bull_score = round(bull_score, 3)
bear_score = round(bear_score, 3)

if bull_score > bear_score + 0.15:
    master_signal = "BULLISH"
    master_color = "#4f8"
elif bear_score > bull_score + 0.15:
    master_signal = "BEARISH"
    master_color = "#f84"
elif bull_score > bear_score:
    master_signal = "LEANING BULLISH"
    master_color = "#af8"
elif bear_score > bull_score:
    master_signal = "LEANING BEARISH"
    master_color = "#fa8"
else:
    master_signal = "NEUTRAL"
    master_color = "#888"

total_score = bull_score + bear_score
master_confidence = round(max(bull_score, bear_score) / total_score * 100, 1) if total_score > 0 else 0

# HTML generation
def signal_color(signal):
    if signal == "BULLISH": return "#4f8"
    if signal == "BEARISH": return "#f84"
    if signal == "MIXED": return "#fa8"
    if signal == "LEANING BULLISH": return "#af8"
    if signal == "LEANING BEARISH": return "#fa8"
    return "#888"

def strength_color(strength):
    if strength == "STRONG": return "#4f8"
    if strength == "MEDIUM": return "#fa8"
    if strength == "CONFLICTING": return "#f8a"
    return "#888"

bullish_gens = [r["gen"] for r in results if r["signal"] == "BULLISH"]
bearish_gens = [r["gen"] for r in results if r["signal"] == "BEARISH"]
mixed_gens = [r["gen"] for r in results if r["signal"] == "MIXED"]
neutral_gens = [r["gen"] for r in results if r["signal"] in ["NEUTRAL"]]

html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Signal — Defence ETF</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; max-width:900px; }}
  .master {{ background:#1a1a1a; border:1px solid #333; border-radius:8px; padding:20px; margin-bottom:20px; }}
  .gen-summary {{ background:#161616; border:1px solid #222; border-radius:6px; padding:14px; margin:8px 0; }}
  .pattern-item {{ background:#1e1e1e; border-left:3px solid #333; padding:6px 10px; margin:4px 0; font-size:11px; border-radius:3px; }}
  .price-zone {{ background:#1a1a2a; border:1px solid #2a2a3a; padding:6px 10px; margin:6px 0; font-size:11px; border-radius:3px; color:#8af; }}
  h2 {{ color:#4af; margin:0 0 4px 0; }}
  h3 {{ color:#666; margin:0 0 8px 0; font-size:11px; }}
  .divider {{ border:none; border-top:1px solid #222; margin:10px 0; }}
</style>
</head>
<body>

<div class="master">
  <h2>FMS — DEFENCE ETF</h2>
  <h3>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h3>
  <div style="font-size:32px; color:{master_color}; font-weight:bold; margin:12px 0;">{master_signal}</div>
  <div style="color:#666; font-size:11px; margin-bottom:8px;">
    Bull score: {bull_score} | Bear score: {bear_score} | Confidence: {master_confidence}%
  </div>
  <hr class="divider">
  <div style="font-size:11px; color:#555;">
    {"✅ Bullish: " + ", ".join(bullish_gens) if bullish_gens else ""}
    {"⚠️ Mixed: " + ", ".join(mixed_gens) if mixed_gens else ""}
    {"🔴 Bearish: " + ", ".join(bearish_gens) if bearish_gens else ""}
    {"⬜ Neutral: " + ", ".join(neutral_gens) if neutral_gens else ""}
  </div>
</div>

'''

for r in reversed(results):
    sig_color = signal_color(r["signal"])
    str_color = strength_color(r["strength"])
    dir_arrow = "↑" if r["direction"] == "UP" else "↓"

    html += f'''<div class="gen-summary">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
    <div>
      <span style="color:#aaa; font-size:14px; font-weight:bold;">{r["gen"]}</span>
      <span style="color:#444; font-size:11px; margin-left:8px;">{r["span"]}</span>
    </div>
    <div style="text-align:right;">
      <span style="color:{sig_color}; font-size:15px; font-weight:bold;">{r["signal"]}</span>
      <span style="color:{str_color}; font-size:10px; margin-left:6px;">{r["strength"]}</span>
    </div>
  </div>
  <div style="color:#555; font-size:11px; margin-bottom:6px;">
    {dir_arrow} {r["direction"]} {r["degree"]}° | X={r["X"]} Y={r["Y"]} Y/X={r["Y_X"]}
  </div>
  <div class="price-zone">{r["price_zone"]}</div>
  <div style="color:#555; font-size:11px; margin:6px 0;">{r["note"]}</div>
'''

    if r["fired_patterns"]:
        html += '  <div style="margin-top:6px;">\n'
        for p in r["fired_patterns"]:
            exc_str = f'+{p["excess"]}%' if p["excess"] >= 0 else f'{p["excess"]}%'
            count_str = f'×{p["count"]}' if p["count"] > 1 else ""
            html += f'''  <div class="pattern-item" style="border-color:{signal_color(p["signal"])}">
    {p["signal"]} {count_str} | {p["position"]} half | consumption {p["tier"]} | excess {exc_str} | {p["strength"]} | {p["note"]}
  </div>
'''
        html += '  </div>\n'

    html += '</div>\n'

html += '</body></html>'

with open('fms_signal_defence.html', 'w') as f:
    f.write(html)

print("Saved: fms_signal_defence.html")
print(f"\nMASTER: {master_signal} | Confidence: {master_confidence}%")
print(f"Bull: {bull_score} | Bear: {bear_score}")
print()
for r in reversed(results):
    print(f"{r['gen']} ({r['span']}): {r['signal']} — {r['strength']}")
    print(f"  Direction: {r['direction']} | Price: {r['current_price']} | {r['price_zone']}")
    for p in r['fired_patterns']:
        print(f"  → {p['signal']} ×{p['count']} | {p['position']} | {p['tier']} | excess {p['excess']}%")
    print()

