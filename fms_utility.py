import sqlite3
import yfinance as yf
import pandas as pd
from kiteconnect import KiteConnect
from datetime import datetime, timedelta

DB_PATH = 'fms.db'
api_key = "tsm9w570sr8un8kj"
access_token = "Ika9gOlRs1KUm3bnJhEEKUVjCr4Fqcc7"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

MACRO_SOURCES = {
    'oil':     'BZ=F',
    'gas':     'NG=F',
    'usd_inr': 'INR=X',
    'usd_cny': 'CNY=X'
}

MACRO_COLORS = {
    'oil':     '#ff4444',
    'gas':     '#ffaa00',
    'usd_inr': '#4488ff',
    'usd_cny': '#44ff88'
}

MACRO_LABELS = {
    'oil': 'Oil', 'gas': 'Gas',
    'usd_inr': 'USD/INR', 'usd_cny': 'USD/CNY'
}

# USD/INR is inverse - expected behavior is opposite direction
INVERSE_FACTORS = {'usd_inr'}

def fetch_hourly_macro():
    macro_data = {}
    for factor, symbol in MACRO_SOURCES.items():
        try:
            df = yf.Ticker(symbol).history(period='1mo', interval='1h')
            df['change_pct'] = df['Close'].pct_change() * 100
            df = df.dropna(subset=['change_pct'])
            threshold = df['change_pct'].abs().quantile(0.90)
            df['is_spike'] = df['change_pct'].abs() >= threshold
            df.index = pd.to_datetime(df.index, utc=True)
            macro_data[factor] = {'df': df, 'threshold': threshold}
            spikes = df['is_spike'].sum()
            print(f"  {factor}: {len(df)} hourly candles | threshold={round(threshold,3)}% | spikes={spikes}")
        except Exception as e:
            print(f"  {factor}: ERROR - {e}")
    return macro_data

def fetch_hourly_defence():
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    candles = kite.historical_data(6385665, from_date, to_date, '60minute')
    print(f"  Defence ETF hourly: {len(candles)} candles")
    return candles

def fetch_daily_defence():
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    candles = kite.historical_data(6385665, from_date, to_date, 'day')
    print(f"  Defence ETF daily: {len(candles)} candles")
    return candles

def calculate_hourly_volume_attribution(hourly_candles, macro_data):
    daily_attribution = {}

    for candle in hourly_candles:
        try:
            candle_time_utc = candle['date'].astimezone(
                __import__('datetime').timezone.utc
            )
        except:
            candle_time_utc = candle['date']

        date_str = candle['date'].strftime('%Y-%m-%d')
        vol = candle['volume']

        if date_str not in daily_attribution:
            daily_attribution[date_str] = {
                'independent': 0,
                'oil': 0, 'gas': 0, 'usd_inr': 0, 'usd_cny': 0,
                'oil_direction': 0, 'gas_direction': 0,
                'usd_inr_direction': 0, 'usd_cny_direction': 0,
                'total': 0
            }

        daily_attribution[date_str]['total'] += vol

        spiked_factors = []
        for factor, mdata in macro_data.items():
            df = mdata['df']
            try:
                hour_str = candle_time_utc.strftime('%Y-%m-%d %H')
                matching = df[df.index.strftime('%Y-%m-%d %H') == hour_str]
                if not matching.empty and matching.iloc[0]['is_spike']:
                    spiked_factors.append((factor, float(matching.iloc[0]['change_pct'])))
            except:
                pass

        if spiked_factors:
            vol_per_factor = vol / len(spiked_factors)
            for factor, chg in spiked_factors:
                daily_attribution[date_str][factor] += vol_per_factor
                daily_attribution[date_str][factor + '_direction'] += chg
        else:
            daily_attribution[date_str]['independent'] += vol

    return daily_attribution

def generate_utility_visual(daily_candles, hourly_candles, macro_data, daily_attribution):
    closes = [c['close'] for c in daily_candles]
    volumes = [c['volume'] for c in daily_candles]
    dates = [c['date'].strftime('%Y-%m-%d') for c in daily_candles]

    price_min = min(closes)
    price_max = max(closes)
    price_mid = (price_min + price_max) / 2
    price_range = price_max - price_min if price_max != price_min else 1

    global_max_vol = max(volumes) if volumes else 1

    def vol_to_size(v, max_v=None, min_size=2, max_size=20):
        if max_v is None:
            max_v = global_max_vol
        if max_v == 0:
            return min_size
        return min_size + (v / max_v) * (max_size - min_size)

    svg_width = 1300
    svg_height = 320
    padding_left = 55
    padding_right = 20
    padding_top = 50
    padding_bottom = 45

    n = len(daily_candles)
    x_step = (svg_width - padding_left - padding_right) / (n - 1) if n > 1 else 1

    def price_to_y(p):
        return svg_height - padding_bottom - ((p - price_min) / price_range) * (svg_height - padding_top - padding_bottom)

    svg_elements = []

    # Reference lines
    for p, label in [(price_max, f'{price_max:.1f}'), (price_mid, f'{price_mid:.1f}'), (price_min, f'{price_min:.1f}')]:
        y = price_to_y(p)
        col = '#333' if p == price_mid else '#2a2a2a'
        svg_elements.append(f'<line x1="{padding_left}" y1="{y:.1f}" x2="{svg_width-padding_right}" y2="{y:.1f}" stroke="{col}" stroke-width="0.8" stroke-dasharray="4,4"/>')
        svg_elements.append(f'<text x="{padding_left-4}" y="{y+3:.1f}" fill="#444" font-size="8" text-anchor="end">{label}</text>')

    # Connect circles
    for i in range(1, n):
        x1 = padding_left + (i-1) * x_step
        y1 = price_to_y(closes[i-1])
        x2 = padding_left + i * x_step
        y2 = price_to_y(closes[i])
        svg_elements.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#2a2a2a" stroke-width="0.8"/>')

    # Draw circles and squares
    for i, (date, close, vol) in enumerate(zip(dates, closes, volumes)):
        cx = padding_left + i * x_step
        cy = price_to_y(close)

        attr = daily_attribution.get(date, None)

        # Circle = independent volume, always neutral grey/white
        if attr and attr['total'] > 0:
            indep_vol = attr['independent']
        else:
            indep_vol = vol

        circle_size = vol_to_size(indep_vol)
        svg_elements.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{circle_size:.1f}" fill="none" stroke="#bbbbbb" stroke-width="1.5" opacity="0.7"/>')

        # Squares = macro attributed volume
        if attr:
            sq_x_base = cx + circle_size + 3
            sq_stack = 0

            for factor in ['oil', 'gas', 'usd_inr', 'usd_cny']:
                factor_vol = attr.get(factor, 0)
                if factor_vol > 0:
                    sq_size = vol_to_size(factor_vol, max_v=global_max_vol, max_size=14, min_size=2)
                    sq_x = sq_x_base
                    sq_y = cy - sq_size/2 - sq_stack

                    color = MACRO_COLORS[factor]

                    # Determine followed or diverged
                    stock_up = i > 0 and closes[i] > closes[i-1]
                    macro_dir = attr.get(factor + '_direction', 0)
                    macro_up = macro_dir > 0

                    if factor in INVERSE_FACTORS:
                        followed = stock_up != macro_up
                    else:
                        followed = stock_up == macro_up

                    # Solid filled = followed expected behavior
                    # Hollow outline = diverged from expected
                    if followed:
                        svg_elements.append(f'<rect x="{sq_x:.1f}" y="{sq_y:.1f}" width="{sq_size:.1f}" height="{sq_size:.1f}" fill="{color}" opacity="0.9" stroke="{color}" stroke-width="1"/>')
                    else:
                        svg_elements.append(f'<rect x="{sq_x:.1f}" y="{sq_y:.1f}" width="{sq_size:.1f}" height="{sq_size:.1f}" fill="none" opacity="0.9" stroke="{color}" stroke-width="1.5"/>')

                    sq_stack += sq_size + 2

        # Date label every 15 days
        if i % 15 == 0:
            svg_elements.append(f'<text x="{cx:.1f}" y="{svg_height-padding_bottom+14}" fill="#333" font-size="7" text-anchor="middle">{date[5:]}</text>')

    # Legend
    lx = padding_left
    ly = 18
    svg_elements.append(f'<circle cx="{lx+5}" cy="{ly}" r="5" fill="none" stroke="#bbbbbb" stroke-width="1.5"/>')
    svg_elements.append(f'<text x="{lx+13}" y="{ly+4}" fill="#666" font-size="8">Independent vol</text>')
    lx += 110

    for factor, color in MACRO_COLORS.items():
        svg_elements.append(f'<rect x="{lx}" y="{ly-5}" width="7" height="7" fill="{color}"/>')
        svg_elements.append(f'<text x="{lx+10}" y="{ly+3}" fill="#666" font-size="8">{MACRO_LABELS[factor]}</text>')
        lx += 70

    svg_elements.append(f'<rect x="{lx+10}" y="{ly-5}" width="7" height="7" fill="#888" opacity="0.9"/>')
    svg_elements.append(f'<text x="{lx+20}" y="{ly+3}" fill="#555" font-size="8">filled=followed</text>')
    lx += 100
    svg_elements.append(f'<rect x="{lx+10}" y="{ly-5}" width="7" height="7" fill="none" stroke="#888" stroke-width="1.5"/>')
    svg_elements.append(f'<text x="{lx+20}" y="{ly+3}" fill="#555" font-size="8">hollow=diverged</text>')

    svg = f'<svg width="{svg_width}" height="{svg_height}" style="background:#151515; border-radius:8px; border:1px solid #2a2a2a">{"".join(svg_elements)}</svg>'

    # Summary table
    total_vol_all = sum(c['volume'] for c in daily_candles)

    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Utility — Defence ETF</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; }}
  h1 {{ color:#4af; margin-bottom:4px; }}
  .section {{ background:#161616; border:1px solid #222; border-radius:6px; padding:16px; margin-bottom:16px; }}
  h2 {{ color:#666; font-size:11px; margin:0 0 10px 0; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ color:#555; font-size:11px; text-align:left; padding:4px 8px; border-bottom:1px solid #222; }}
  td {{ font-size:11px; padding:4px 8px; border-bottom:1px solid #1a1a1a; color:#aaa; }}
</style>
</head>
<body>
<h1>FMS Utility — Defence ETF Correlation Visual</h1>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 6 months daily | Hourly volume attribution</p>

<div class="section">
<h2>⬤ Circle = independent volume (neutral) | ■ Filled square = macro factor followed expected | □ Hollow square = macro factor diverged | Circle + Squares = total daily volume</h2>
{svg}
</div>

<div class="section">
<h2>VOLUME ATTRIBUTION SUMMARY (last 30 days)</h2>
<table>
<tr>
  <th>Factor</th>
  <th>Days attributed</th>
  <th>Total volume</th>
  <th>Avg vol/day</th>
  <th>% of total</th>
  <th>Followed</th>
  <th>Diverged</th>
</tr>'''

    for factor, color in MACRO_COLORS.items():
        factor_vol = sum(d.get(factor, 0) for d in daily_attribution.values())
        factor_days = sum(1 for d in daily_attribution.values() if d.get(factor, 0) > 0)
        avg_vol = round(factor_vol / factor_days) if factor_days > 0 else 0
        pct = round(factor_vol / total_vol_all * 100, 1) if total_vol_all > 0 else 0

        followed = 0
        diverged = 0
        for date, attr in daily_attribution.items():
            if attr.get(factor, 0) > 0 and date in dates:
                idx = dates.index(date)
                if idx > 0:
                    stock_up = closes[idx] > closes[idx-1]
                    macro_up = attr.get(factor + '_direction', 0) > 0
                    if factor in INVERSE_FACTORS:
                        if stock_up != macro_up:
                            followed += 1
                        else:
                            diverged += 1
                    else:
                        if stock_up == macro_up:
                            followed += 1
                        else:
                            diverged += 1

        html += f'''<tr>
<td style="color:{color};">{MACRO_LABELS[factor]}</td>
<td>{factor_days}</td>
<td>{int(factor_vol):,}</td>
<td>{avg_vol:,}</td>
<td>{pct}%</td>
<td style="color:#4f8;">{followed}</td>
<td style="color:#f84;">{diverged}</td>
</tr>'''

    indep_vol = sum(d.get('independent', 0) for d in daily_attribution.values())
    indep_days = sum(1 for d in daily_attribution.values() if d.get('independent', 0) > 0)
    indep_pct = round(indep_vol / total_vol_all * 100, 1) if total_vol_all > 0 else 0

    html += f'''<tr>
<td style="color:#bbbbbb;">Independent</td>
<td>{indep_days}</td>
<td>{int(indep_vol):,}</td>
<td>{round(indep_vol/indep_days) if indep_days > 0 else 0:,}</td>
<td>{indep_pct}%</td>
<td>—</td>
<td>—</td>
</tr>'''

    html += '''</table>
</div>
</body></html>'''

    with open('fms_utility.html', 'w') as f:
        f.write(html)
    print("Saved: fms_utility.html")

# Run
print("Fetching hourly macro data...")
macro_data = fetch_hourly_macro()

print("\nFetching Defence ETF data...")
hourly_candles = fetch_hourly_defence()
daily_candles = fetch_daily_defence()

print("\nCalculating hourly volume attribution...")
daily_attribution = calculate_hourly_volume_attribution(hourly_candles, macro_data)
print(f"  {len(daily_attribution)} days with hourly attribution")

print("\nGenerating visual...")
generate_utility_visual(hourly_candles, hourly_candles, macro_data, daily_attribution)
print("Open: open fms_utility.html")
