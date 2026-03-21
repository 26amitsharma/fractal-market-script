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
    'oil':     {'square': '#ff4444', 'label': 'Oil'},
    'gas':     {'square': '#ffaa00', 'label': 'Gas'},
    'usd_inr': {'square': '#4488ff', 'label': 'USD/INR'},
    'usd_cny': {'square': '#44ff88', 'label': 'USD/CNY'}
}

def fetch_hourly_macro():
    """Fetch hourly macro data for all 4 factors"""
    macro_data = {}
    for factor, symbol in MACRO_SOURCES.items():
        try:
            df = yf.Ticker(symbol).history(period='1mo', interval='1h')
            df['change_pct'] = df['Close'].pct_change() * 100
            df = df.dropna(subset=['change_pct'])
            threshold = df['change_pct'].abs().quantile(0.90)
            df['is_spike'] = df['change_pct'].abs() >= threshold
            macro_data[factor] = df
            print(f"  {factor}: {len(df)} hourly candles, threshold={round(threshold,3)}%")
        except Exception as e:
            print(f"  {factor}: ERROR - {e}")
    return macro_data

def fetch_hourly_defence():
    """Fetch hourly Defence ETF data from Zerodha"""
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    candles = kite.historical_data(6385665, from_date, to_date, '60minute')
    print(f"  Defence ETF: {len(candles)} hourly candles")
    return candles

def fetch_daily_defence():
    """Fetch 6 months daily Defence ETF data"""
    to_date = datetime.now()
    from_date = to_date - timedelta(days=180)
    candles = kite.historical_data(6385665, from_date, to_date, 'day')
    print(f"  Defence ETF daily: {len(candles)} candles")
    return candles

def generate_utility_visual(daily_candles, hourly_candles, macro_data):
    """Generate the correlation visual page"""

    # Process daily data
    closes = [c['close'] for c in daily_candles]
    volumes = [c['volume'] for c in daily_candles]
    dates = [c['date'].strftime('%Y-%m-%d') for c in daily_candles]

    avg_vol = sum(volumes) / len(volumes)
    max_vol = max(volumes)
    min_vol = min(volumes)
    price_min = min(closes)
    price_max = max(closes)
    price_mid = (price_min + price_max) / 2
    price_range = price_max - price_min if price_max != price_min else 1

    # Process hourly data - find spike hours per day per factor
    daily_macro_spikes = {}  # date -> {factor -> spike_info}

    for factor, df in macro_data.items():
        spike_rows = df[df['is_spike'] == True]
        for idx, row in spike_rows.iterrows():
            date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
            if date_str not in daily_macro_spikes:
                daily_macro_spikes[date_str] = {}
            if factor not in daily_macro_spikes[date_str]:
                daily_macro_spikes[date_str][factor] = []
            daily_macro_spikes[date_str][factor].append(float(row['change_pct']))

    # Process hourly defence volumes on spike hours
    hourly_defence_by_date = {}
    avg_hourly_vol = sum(c['volume'] for c in hourly_candles) / len(hourly_candles) if hourly_candles else 1

    for c in hourly_candles:
        date_str = c['date'].strftime('%Y-%m-%d')
        if date_str not in hourly_defence_by_date:
            hourly_defence_by_date[date_str] = []
        hourly_defence_by_date[date_str].append(c['volume'])

    # SVG dimensions
    svg_width = 1300
    svg_height = 300
    padding_left = 50
    padding_right = 20
    padding_top = 40
    padding_bottom = 40

    n = len(daily_candles)
    x_step = (svg_width - padding_left - padding_right) / (n - 1) if n > 1 else 1

    def price_to_y(p):
        return svg_height - padding_bottom - ((p - price_min) / price_range) * (svg_height - padding_top - padding_bottom)

    def vol_to_circle_size(v):
        vol_range = max_vol - min_vol if max_vol != min_vol else 1
        return 3 + (v - min_vol) / vol_range * 18

    svg_elements = []

    # Reference lines
    y_ceil = price_to_y(price_max)
    y_mid = price_to_y(price_mid)
    y_floor = price_to_y(price_min)

    svg_elements.append(f'<line x1="{padding_left}" y1="{y_ceil:.1f}" x2="{svg_width-padding_right}" y2="{y_ceil:.1f}" stroke="#2a2a2a" stroke-width="0.8" stroke-dasharray="4,4"/>')
    svg_elements.append(f'<line x1="{padding_left}" y1="{y_mid:.1f}" x2="{svg_width-padding_right}" y2="{y_mid:.1f}" stroke="#333" stroke-width="0.8" stroke-dasharray="4,4"/>')
    svg_elements.append(f'<line x1="{padding_left}" y1="{y_floor:.1f}" x2="{svg_width-padding_right}" y2="{y_floor:.1f}" stroke="#2a2a2a" stroke-width="0.8" stroke-dasharray="4,4"/>')

    svg_elements.append(f'<text x="{padding_left-4}" y="{y_ceil:.1f}" fill="#444" font-size="8" text-anchor="end">{price_max:.1f}</text>')
    svg_elements.append(f'<text x="{padding_left-4}" y="{y_mid:.1f}" fill="#444" font-size="8" text-anchor="end">{price_mid:.1f}</text>')
    svg_elements.append(f'<text x="{padding_left-4}" y="{y_floor:.1f}" fill="#444" font-size="8" text-anchor="end">{price_min:.1f}</text>')

    # Connect circles with line
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
        circle_size = vol_to_circle_size(vol)

        # Circle color based on direction
        if i > 0:
            circle_color = '#4f8' if close > closes[i-1] else '#f84'
        else:
            circle_color = '#888'

        # Draw main circle
        svg_elements.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{circle_size:.1f}" fill="none" stroke="{circle_color}" stroke-width="1.2" opacity="0.7"/>')

        # Draw squares for macro spikes
        if date in daily_macro_spikes:
            square_offset = -circle_size - 4
            for factor_idx, (factor, spike_changes) in enumerate(daily_macro_spikes[date].items()):
                color = MACRO_COLORS[factor]['square']
                max_spike = max(abs(c) for c in spike_changes)

                # Square size based on spike magnitude
                sq_size = 3 + min(max_spike * 1.5, 12)

                # Stack squares horizontally if multiple factors
                sq_x = cx - sq_size/2 + factor_idx * (sq_size + 2)
                sq_y = cy + square_offset - factor_idx * (sq_size + 2)

                # Did stock follow this factor?
                stock_direction = 1 if i > 0 and close > closes[i-1] else -1
                macro_direction = 1 if sum(spike_changes) > 0 else -1

                # For usd_inr, inverse relationship
                expected_follow = macro_direction if factor != 'usd_inr' else -macro_direction
                followed = stock_direction == expected_follow

                opacity = '0.9' if followed else '0.5'
                stroke = '#fff' if followed else '#888'

                svg_elements.append(f'<rect x="{sq_x:.1f}" y="{sq_y:.1f}" width="{sq_size:.1f}" height="{sq_size:.1f}" fill="{color}" opacity="{opacity}" stroke="{stroke}" stroke-width="0.5"/>')

        # Date label every 15 days
        if i % 15 == 0:
            svg_elements.append(f'<text x="{cx:.1f}" y="{svg_height-padding_bottom+12}" fill="#333" font-size="7" text-anchor="middle">{date[5:]}</text>')

    # Legend
    legend_x = padding_left
    legend_y = 15
    for factor, colors in MACRO_COLORS.items():
        svg_elements.append(f'<rect x="{legend_x}" y="{legend_y-6}" width="8" height="8" fill="{colors["square"]}"/>')
        svg_elements.append(f'<text x="{legend_x+11}" y="{legend_y+1}" fill="#888" font-size="8">{colors["label"]}</text>')
        legend_x += 70

    svg_elements.append(f'<text x="{legend_x+20}" y="{legend_y+1}" fill="#555" font-size="8">■ bright=followed expected | ■ dim=diverged</text>')

    svg = f'<svg width="{svg_width}" height="{svg_height}" style="background:#151515; border-radius:8px; border:1px solid #2a2a2a">{"".join(svg_elements)}</svg>'

    # HTML page
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Utility — Defence ETF Correlation Visual</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; }}
  h1 {{ color:#4af; margin-bottom:4px; }}
  .section {{ background:#161616; border:1px solid #222; border-radius:6px; padding:16px; margin-bottom:16px; }}
  h2 {{ color:#666; font-size:12px; margin:0 0 10px 0; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ color:#555; font-size:11px; text-align:left; padding:4px 8px; border-bottom:1px solid #222; }}
  td {{ font-size:11px; padding:4px 8px; border-bottom:1px solid #1a1a1a; color:#aaa; }}
</style>
</head>
<body>
<h1>FMS Utility — Defence ETF</h1>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Last 6 months daily | Squares = macro spike hours</p>

<div class="section">
<h2>CORRELATION VISUAL — Circle=daily stock move (size=volume) | Square=macro spike day (color=factor, bright=expected follow, dim=diverged)</h2>
{svg}
</div>

<div class="section">
<h2>MACRO SPIKE SUMMARY</h2>
<table>
<tr><th>Factor</th><th>Spike Days (last 30 days)</th><th>Defence Followed</th><th>Defence Diverged</th><th>Follow Rate</th></tr>
'''

    for factor in MACRO_COLORS:
        spike_dates = [d for d in daily_macro_spikes if factor in daily_macro_spikes[d]]
        followed = 0
        diverged = 0
        for date in spike_dates:
            if date in dates:
                idx = dates.index(date)
                if idx > 0:
                    stock_up = closes[idx] > closes[idx-1]
                    macro_up = sum(daily_macro_spikes[date][factor]) > 0
                    if factor == 'usd_inr':
                        expected = not macro_up
                    else:
                        expected = macro_up
                    if stock_up == expected:
                        followed += 1
                    else:
                        diverged += 1

        total = followed + diverged
        follow_rate = f"{round(followed/total*100,1)}%" if total > 0 else "N/A"
        color = MACRO_COLORS[factor]['square']

        html += f'''<tr>
<td style="color:{color};">{factor}</td>
<td>{len(spike_dates)}</td>
<td style="color:#4f8;">{followed}</td>
<td style="color:#f84;">{diverged}</td>
<td>{follow_rate}</td>
</tr>'''

    html += '''</table>
</div>
</body></html>'''

    with open('fms_utility.html', 'w') as f:
        f.write(html)
    print("Utility visual saved: fms_utility.html")

# Run
print("Fetching hourly macro data...")
macro_data = fetch_hourly_macro()

print("\nFetching Defence ETF data...")
hourly_candles = fetch_hourly_defence()
daily_candles = fetch_daily_defence()

print("\nGenerating visual...")
generate_utility_visual(daily_candles, hourly_candles, macro_data)
print("Open: open fms_utility.html")
