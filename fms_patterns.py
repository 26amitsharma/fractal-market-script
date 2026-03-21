from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from collections import defaultdict

api_key = "tsm9w570sr8un8kj"
access_token = "Ika9gOlRs1KUm3bnJhEEKUVjCr4Fqcc7"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

INSTRUMENT = 6385665  # DEFENCE ETF

GENERATIONS = [
    ("minute",   "G1", 1,    5),
    ("15minute", "G2", 15,   30),
    ("day",      "G3", 390,  180),
    ("week",     "G4", 1950, 800),
]

def fetch_all(instrument_token, interval, days):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    return kite.historical_data(
        instrument_token=instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval=interval
    )

def calculate_baseline(candles):
    """Calculate random baseline probability of both-up for this generation"""
    closes = [c['close'] for c in candles]
    both_up_count = 0
    total = 0
    for i in range(len(closes) - 2):
        if closes[i+1] > closes[i] and closes[i+2] > closes[i]:
            both_up_count += 1
        total += 1
    return round(both_up_count / total * 100, 1) if total > 0 else 33.0

def consumption_tier(consumed, total_nearby):
    """Classify consumption as 100%, 99-50%, or <50%"""
    if total_nearby == 0:
        return "100%"  # no smaller circles nearby = complete dominance
    pct = consumed / total_nearby
    if pct >= 1.0:
        return "100%"
    elif pct >= 0.5:
        return "50-99%"
    else:
        return "<50%"

def analyze_generation(candles, gen_label):
    records = []
    n = len(candles)
    if n < 5:
        return records, 33.0

    closes = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]
    avg_vol = sum(volumes) / len(volumes) if sum(volumes) > 0 else 1
    max_vol = max(volumes)
    price_min = min(closes)
    price_max = max(closes)
    price_range = price_max - price_min if price_max != price_min else 1
    center = (price_min + price_max) / 2

    # Generation baseline
    baseline = calculate_baseline(candles)

    for i in range(2, n - 2):
        v = volumes[i]
        c = closes[i]

        if v < avg_vol:
            continue

        position = "upper" if c > center else "lower"
        size_ratio = round(v / avg_vol, 2)

        # Radius = 15% of price range scaled by relative volume
        radius = (v / max_vol) * 0.15 * price_range

        # Find all smaller circles within radius (window of 7 candles around)
        nearby_smaller = []
        for j in range(max(0, i-3), min(n, i+4)):
            if j != i and volumes[j] < v and abs(closes[j] - c) <= radius:
                nearby_smaller.append(j)

        # Total smaller circles in window regardless of radius
        total_smaller_in_window = sum(
            1 for j in range(max(0, i-3), min(n, i+4))
            if j != i and volumes[j] < v
        )

        consumed = len(nearby_smaller)
        tier = consumption_tier(consumed, total_smaller_in_window)

        # Next 2 and next 5 circles
        next1 = candles[i+1]
        next2 = candles[i+2]

        next1_dir = "up" if next1['close'] > c else "down"
        next2_dir = "up" if next2['close'] > c else "down"

        avg_step = price_range / n if n > 0 else 1
        next1_dist = round(abs(next1['close'] - c) / avg_step, 2)
        next2_dist = round(abs(next2['close'] - c) / avg_step, 2)

        both_up = next1_dir == "up" and next2_dir == "up"
        both_down = next1_dir == "down" and next2_dir == "down"
        mixed = not both_up and not both_down

        records.append({
            "gen": gen_label,
            "timestamp": candles[i]['date'],
            "price": round(c, 2),
            "position": position,
            "size_ratio": size_ratio,
            "consumption_tier": tier,
            "consumed": consumed,
            "total_nearby": total_smaller_in_window,
            "next1_dir": next1_dir,
            "next1_dist": next1_dist,
            "next2_dir": next2_dir,
            "next2_dist": next2_dist,
            "both_up": both_up,
            "both_down": both_down,
            "mixed": mixed
        })

    return records, baseline

# Collect all records
all_records = []
baselines = {}

for interval, gen_label, interval_mins, days in GENERATIONS:
    print(f"Fetching {gen_label}...")
    candles = fetch_all(INSTRUMENT, interval, days)
    records, baseline = analyze_generation(candles, gen_label)
    baselines[gen_label] = baseline
    all_records.extend(records)
    print(f"  {len(candles)} candles → {len(records)} large circle events | baseline both-up: {baseline}%")

print("\nGeneration baselines (random both-up probability):")
for gen, b in baselines.items():
    print(f"  {gen}: {b}%")

# Pattern summaries
pattern_buckets = defaultdict(list)
for r in all_records:
    key = (r['gen'], r['position'], r['consumption_tier'])
    pattern_buckets[key].append(r)

print("\n" + "="*105)
print(f"{'PATTERN':<45} {'COUNT':>6} {'BOTH_UP%':>9} {'BASELINE':>9} {'EXCESS':>8} {'BOTH_DN%':>9} {'AVG_DIST':>9} {'SIGNAL':>10}")
print("="*105)

# Sort by excess signal strength
rows = []
for (gen, pos, tier), records in pattern_buckets.items():
    count = len(records)
    if count < 3:
        continue
    both_up_pct = round(sum(1 for r in records if r['both_up']) / count * 100, 1)
    both_dn_pct = round(sum(1 for r in records if r['both_down']) / count * 100, 1)
    avg_dist = round(sum(r['next1_dist'] + r['next2_dist'] for r in records) / count / 2, 2)
    baseline = baselines.get(gen, 33.0)
    excess = round(both_up_pct - baseline, 1)

    if abs(excess) >= 15:
        signal = "STRONG"
    elif abs(excess) >= 8:
        signal = "MEDIUM"
    else:
        signal = "NOISE"

    pattern = f"{gen} | {pos} | consumption={tier}"
    rows.append((excess, pattern, count, both_up_pct, baseline, excess, both_dn_pct, avg_dist, signal))

rows.sort(key=lambda x: x[0], reverse=True)

for _, pattern, count, both_up_pct, baseline, excess, both_dn_pct, avg_dist, signal in rows:
    excess_str = f"+{excess}%" if excess >= 0 else f"{excess}%"
    print(f"{pattern:<45} {count:>6} {both_up_pct:>8}% {baseline:>8}% {excess_str:>8} {both_dn_pct:>8}% {avg_dist:>9} {signal:>10}")

print("="*105)
print(f"\nTotal events: {len(all_records)}")
print(f"Strong signals: {sum(1 for r in rows if r[-1]=='STRONG')}")
print(f"Medium signals: {sum(1 for r in rows if r[-1]=='MEDIUM')}")
print(f"Noise: {sum(1 for r in rows if r[-1]=='NOISE')}")

