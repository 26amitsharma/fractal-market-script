import sqlite3
import yfinance as yf
import pandas as pd
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import pytz

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

# Verified reliability from fms_verify
RELIABILITY = {
    'oil':     {'tailwind': ('60%', 'MODERATE'), 'headwind': ('60%', 'MODERATE')},
    'gas':     {'tailwind': ('50%', 'NOISE'),    'headwind': ('33%', 'NOISE')},
    'usd_inr': {'tailwind': ('57%', 'NEUTRAL'),  'headwind': ('80%', 'STRONG')},
    'usd_cny': {'tailwind': ('83%', 'STRONG'),   'headwind': ('50%', 'NEUTRAL')},
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_support_resistance(zerodha_token, current_price):
    """Get support and resistance levels from large volume daily candles"""
    from datetime import datetime, timedelta
    to_date = datetime.now()
    from_date = to_date - timedelta(days=365)
    
    try:
        candles = kite.historical_data(zerodha_token, from_date, to_date, 'day')
    except:
        return [], []
    
    if not candles:
        return [], []
    
    avg_vol = sum(c['volume'] for c in candles) / len(candles)
    
    # Large circles = above average volume
    large = [c for c in candles if c['volume'] > avg_vol]
    
    # Support = large circles below current price, sorted by recency
    support = sorted(
        [c for c in large if c['close'] < current_price],
        key=lambda x: x['date'], reverse=True
    )[:3]
    
    # Resistance = large circles above current price, sorted by recency
    resistance = sorted(
        [c for c in large if c['close'] > current_price],
        key=lambda x: x['date'], reverse=True
    )[:3]
    
    max_vol = max(c['volume'] for c in candles) if candles else 1
    
    def enrich(levels):
        return [{
            'price': c['close'],
            'volume': c['volume'],
            'date': c['date'].strftime('%Y-%m-%d'),
            'vol_ratio': round(c['volume'] / max_vol, 3),
            'pct_from_current': round((c['close'] - current_price) / current_price * 100, 1)
        } for c in levels]
    
    return enrich(support), enrich(resistance)

def get_regime_context():
    """Get current regime context for all 4 factors from SQLite"""
    conn = get_db()
    regime = {}

    for factor in MACRO_SOURCES:
        rows = conn.execute('''SELECT date, close FROM macro_daily
                              WHERE factor=? ORDER BY date DESC LIMIT 252''',
                           (factor,)).fetchall()

        if not rows:
            continue

        current = rows[0]['close']
        closes_1y = [r['close'] for r in rows]
        closes_1m = closes_1y[:21]

        high_1y = max(closes_1y)
        low_1y = min(closes_1y)
        high_1m = max(closes_1m)
        low_1m = min(closes_1m)

        all_rows = conn.execute('''SELECT close FROM macro_daily
                                  WHERE factor=? ORDER BY date''',
                               (factor,)).fetchall()
        all_closes = [r['close'] for r in all_rows]
        high_5y = max(all_closes)
        low_5y = min(all_closes)

        def pct(val, low, high):
            r = high - low
            return round((val - low) / r * 100, 1) if r > 0 else 50

        pct_1m = pct(current, low_1m, high_1m)
        pct_1y = pct(current, low_1y, high_1y)
        pct_5y = pct(current, low_5y, high_5y)

        # Regime label based on 1y percentile
        if pct_1y >= 90:
            regime_label = 'EXTREME'
            regime_color = '#f84'
        elif pct_1y >= 70:
            regime_label = 'ELEVATED'
            regime_color = '#fa8'
        elif pct_1y >= 30:
            regime_label = 'NEUTRAL'
            regime_color = '#888'
        elif pct_1y >= 10:
            regime_label = 'DEPRESSED'
            regime_color = '#4af'
        else:
            regime_label = 'EXTREME LOW'
            regime_color = '#44f'

        # Signal bias based on 1m percentile
        if pct_1m >= 80:
            bias = 'Headwinds max reliability'
        elif pct_1m >= 60:
            bias = 'Headwinds stronger'
        elif pct_1m >= 40:
            bias = 'Neutral — both moderate'
        elif pct_1m >= 20:
            bias = 'Tailwinds stronger'
        else:
            bias = 'Tailwinds max reliability'

        regime[factor] = {
            'current': round(current, 3),
            'pct_1m': pct_1m,
            'pct_1y': pct_1y,
            'pct_5y': pct_5y,
            'high_1m': round(high_1m, 3),
            'low_1m': round(low_1m, 3),
            'regime_label': regime_label,
            'regime_color': regime_color,
            'bias': bias
        }

    conn.close()
    return regime

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
        except Exception as e:
            print(f"  {factor}: ERROR - {e}")
    return macro_data

def fetch_hourly_stock(zerodha_token):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    return kite.historical_data(zerodha_token, from_date, to_date, '60minute')

def calculate_attribution(hourly_candles, macro_data):
    attribution = {}
    for candle in hourly_candles:
        try:
            candle_utc = candle['date'].astimezone(pytz.utc)
            key = candle_utc.strftime('%Y-%m-%d %H')
        except:
            key = candle['date'].strftime('%Y-%m-%d %H')

        vol = candle['volume']
        attribution[key] = {
            'independent': 0,
            'oil': 0, 'gas': 0, 'usd_inr': 0, 'usd_cny': 0,
            'oil_dir': 0, 'gas_dir': 0, 'usd_inr_dir': 0, 'usd_cny_dir': 0,
            'total': vol
        }

        spiked = []
        for factor, mdata in macro_data.items():
            df = mdata['df']
            try:
                matching = df[df.index.strftime('%Y-%m-%d %H') == key]
                if not matching.empty and matching.iloc[0]['is_spike']:
                    spiked.append((factor, float(matching.iloc[0]['change_pct'])))
            except:
                pass

        if spiked:
            vol_per = vol / len(spiked)
            for factor, chg in spiked:
                attribution[key][factor] += vol_per
                attribution[key][factor + '_dir'] += chg
        else:
            attribution[key]['independent'] = vol

    return attribution

def generate_supergraph(instrument_name, zerodha_token, progress_callback=None):
    def progress(step, done=False, filename=None):
        if progress_callback: progress_callback(step, done, filename)
    print(f"Building super graph for {instrument_name}...")

    print("  Fetching regime context from SQLite...")
    progress(0)
    regime = get_regime_context()

    print("  Fetching hourly macro data...")
    progress(1)
    macro_data = fetch_hourly_macro()

    print("  Fetching hourly stock data...")
    progress(2)
    hourly_candles = fetch_hourly_stock(zerodha_token)

    print("  Calculating support/resistance levels...")
    current_price = hourly_candles[-1]['close'] if hourly_candles else 0
    support_levels, resistance_levels = get_support_resistance(zerodha_token, current_price)
    progress(3)
    print("  Calculating attribution...")
    progress(3)
    attribution = calculate_attribution(hourly_candles, macro_data)

    # Build graph
    closes = [c['close'] for c in hourly_candles]
    volumes = [c['volume'] for c in hourly_candles]

    import pytz as _pytz
    dates = []
    for c in hourly_candles:
        try:
            dates.append(c['date'].astimezone(_pytz.utc).strftime('%Y-%m-%d %H'))
        except:
            dates.append(c['date'].strftime('%Y-%m-%d %H'))

    display_dates = [c['date'].strftime('%m-%d %H') for c in hourly_candles]

    price_min = min(closes)
    price_max = max(closes)
    
    # Extend range to show nearest support and resistance
    if support_levels:
        price_min = min(price_min, support_levels[0]['price'] * 0.998)
    if resistance_levels:
        price_max = max(price_max, resistance_levels[0]['price'] * 1.002)
    price_mid = (price_min + price_max) / 2
    price_range = price_max - price_min if price_max != price_min else 1
    global_max_vol = max(volumes) if volumes else 1

    def vol_to_size(v, min_size=2, max_size=20):
        return min_size + (v / global_max_vol) * (max_size - min_size)

    svg_width = 1300
    svg_height = 320
    padding_left = 55
    padding_right = 20
    padding_top = 50
    padding_bottom = 45
    n = len(hourly_candles)
    x_step = (svg_width - padding_left - padding_right) / (n - 1) if n > 1 else 1

    def price_to_y(p):
        return svg_height - padding_bottom - ((p - price_min) / price_range) * (svg_height - padding_top - padding_bottom)

    svg_elements = []

    # Reference lines
    for p, label in [(price_max, f'{price_max:.1f}'),
                     (price_mid, f'{price_mid:.1f}'),
                     (price_min, f'{price_min:.1f}')]:
        y = price_to_y(p)
        col = '#333' if p == price_mid else '#2a2a2a'
        svg_elements.append(f'<line x1="{padding_left}" y1="{y:.1f}" x2="{svg_width-padding_right}" y2="{y:.1f}" stroke="{col}" stroke-width="0.8" stroke-dasharray="4,4"/>')
        svg_elements.append(f'<text x="{padding_left-4}" y="{y+3:.1f}" fill="#444" font-size="8" text-anchor="end">{label}</text>')

    # Draw support bands (green) - only nearest S1
    if support_levels:
        s1 = support_levels[0]
        sy = price_to_y(s1['price'])
        band_opacity = round(0.3 + s1['vol_ratio'] * 0.4, 2)
        band_height = max(3, s1['vol_ratio'] * 12)
        svg_elements.append(f'<rect x="{padding_left}" y="{sy:.1f}" width="{svg_width-padding_left-padding_right}" height="{band_height:.1f}" fill="#44ff88" opacity="{band_opacity}" stroke="none"/>')
        svg_elements.append(f'<text x="{svg_width-padding_right-2}" y="{sy-2:.1f}" fill="#44ff88" font-size="8" text-anchor="end" opacity="0.7">S1 {s1["price"]:.1f}</text>')

    # Draw resistance bands (red) - only nearest R1
    if resistance_levels:
        r1 = resistance_levels[0]
        ry = price_to_y(r1['price'])
        band_opacity = round(0.3 + r1['vol_ratio'] * 0.4, 2)
        band_height = max(3, r1['vol_ratio'] * 12)
        svg_elements.append(f'<rect x="{padding_left}" y="{ry:.1f}" width="{svg_width-padding_left-padding_right}" height="{band_height:.1f}" fill="#ff4466" opacity="{band_opacity}" stroke="none"/>')
        svg_elements.append(f'<text x="{svg_width-padding_right-2}" y="{ry-2:.1f}" fill="#ff4466" font-size="8" text-anchor="end" opacity="0.7">R1 {r1["price"]:.1f}</text>')

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
        attr = attribution.get(date, None)

        # Circle = independent volume
        indep_vol = attr['independent'] if attr else vol
        circle_size = vol_to_size(indep_vol)
        svg_elements.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{circle_size:.1f}" fill="none" stroke="#bbbbbb" stroke-width="1.2" opacity="0.7"/>')

        # Squares = macro attributed volume
        if attr:
            stock_up = closes[i] > closes[i-1] if i > 0 else True
            sq_stack = 0

            for factor in ['oil', 'gas', 'usd_inr', 'usd_cny']:
                factor_vol = attr.get(factor, 0)
                if factor_vol <= 0:
                    continue

                sq_size = vol_to_size(factor_vol)
                color = MACRO_COLORS[factor]

                # Regime-adjusted opacity
                reg = regime.get(factor, {})
                pct_1m = reg.get('pct_1m', 50)
                if pct_1m >= 80 or pct_1m <= 20:
                    opacity = '1.0'  # extreme regime = full intensity
                elif pct_1m >= 60 or pct_1m <= 40:
                    opacity = '0.75'  # elevated = medium intensity
                else:
                    opacity = '0.45'  # neutral regime = dim

                sq_x = cx - sq_size/2
                sq_y = cy + circle_size - sq_size - sq_stack

                if stock_up:
                    svg_elements.append(f'<rect x="{sq_x:.1f}" y="{sq_y:.1f}" width="{sq_size:.1f}" height="{sq_size:.1f}" fill="{color}" opacity="{opacity}" stroke="{color}" stroke-width="1"/>')
                else:
                    svg_elements.append(f'<rect x="{sq_x:.1f}" y="{sq_y:.1f}" width="{sq_size:.1f}" height="{sq_size:.1f}" fill="none" opacity="{opacity}" stroke="{color}" stroke-width="1.5"/>')

                sq_stack += sq_size + 1

        # Date label every 6 hours
        if i % 6 == 0:
            svg_elements.append(f'<text x="{cx:.1f}" y="{svg_height-padding_bottom+14}" fill="#333" font-size="7" text-anchor="middle">{display_dates[i]}</text>')

    # Legend
    lx = padding_left
    ly = 18
    svg_elements.append(f'<circle cx="{lx+6}" cy="{ly}" r="5" fill="none" stroke="#bbbbbb" stroke-width="1.2"/>')
    svg_elements.append(f'<text x="{lx+14}" y="{ly+4}" fill="#555" font-size="8">Independent vol</text>')
    lx += 115
    for factor, color in MACRO_COLORS.items():
        svg_elements.append(f'<rect x="{lx}" y="{ly-4}" width="7" height="7" fill="{color}"/>')
        svg_elements.append(f'<text x="{lx+10}" y="{ly+3}" fill="#555" font-size="8">{MACRO_LABELS[factor]}</text>')
        lx += 72
    svg_elements.append(f'<rect x="{lx+10}" y="{ly-4}" width="7" height="7" fill="#888"/>')
    svg_elements.append(f'<text x="{lx+20}" y="{ly+3}" fill="#555" font-size="8">■ tailwind</text>')
    lx += 80
    svg_elements.append(f'<rect x="{lx+10}" y="{ly-4}" width="7" height="7" fill="none" stroke="#888" stroke-width="1.2"/>')
    svg_elements.append(f'<text x="{lx+20}" y="{ly+3}" fill="#555" font-size="8">□ headwind</text>')
    lx += 80
    svg_elements.append(f'<text x="{lx+10}" y="{ly+3}" fill="#444" font-size="8">opacity = regime intensity</text>')

    svg = f'<svg width="{svg_width}" height="{svg_height}" style="background:#151515; border-radius:8px; border:1px solid #2a2a2a">{"".join(svg_elements)}</svg>'

    # Regime table
    regime_rows = ''
    for factor in ['usd_inr', 'usd_cny', 'oil', 'gas']:
        reg = regime.get(factor, {})
        color = MACRO_COLORS[factor]
        rc = reg.get('regime_color', '#888')
        rel_tw = RELIABILITY[factor]['tailwind']
        rel_hw = RELIABILITY[factor]['headwind']

        pct_1m = reg.get('pct_1m', 0)
        pct_1y = reg.get('pct_1y', 0)
        pct_5y = reg.get('pct_5y', 0)

        # Bar visualization for percentiles
        def pct_bar(pct, color):
            w = int(pct * 0.6)
            return f'<div style="display:inline-block;width:60px;background:#1a1a1a;border-radius:2px;height:8px;vertical-align:middle;"><div style="width:{w}px;background:{color};height:8px;border-radius:2px;"></div></div> {pct}%'

        regime_rows += f'''<tr>
<td style="color:{color}; font-weight:bold;">{MACRO_LABELS[factor]}</td>
<td style="color:#eee;">{reg.get("current", "—")}</td>
<td>{pct_bar(pct_1m, rc)}</td>
<td>{pct_bar(pct_1y, rc)}</td>
<td>{pct_bar(pct_5y, rc)}</td>
<td style="color:{rc};">{reg.get("regime_label", "—")}</td>
<td style="color:#888; font-size:10px;">{reg.get("bias", "—")}</td>
<td style="color:#4f8; font-size:10px;">TW: {rel_tw[0]} {rel_tw[1]}</td>
<td style="color:#f84; font-size:10px;">HW: {rel_hw[0]} {rel_hw[1]}</td>
</tr>'''

    # Build HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Super Graph — {instrument_name}</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; }}
  h1 {{ color:#4af; margin-bottom:4px; font-size:18px; }}
  .graph-section {{ background:#161616; border:1px solid #222; border-radius:8px; padding:16px; margin-bottom:8px; }}
  .regime-section {{ background:#161616; border:1px solid #222; border-radius:8px; padding:12px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ color:#444; font-size:10px; text-align:left; padding:4px 8px; border-bottom:1px solid #222; }}
  td {{ font-size:11px; padding:5px 8px; border-bottom:1px solid #1a1a1a; color:#aaa; }}
  h2 {{ color:#555; font-size:11px; margin:0 0 8px 0; }}
</style>
</head>
<body>
<h1>FMS Super Graph — {instrument_name}</h1>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 30 days hourly | Circle=independent vol | Square=macro vol | opacity=regime intensity</p>

<div class="graph-section">
{svg}
</div>

<div class="regime-section">
<h2>MACRO REGIME CONTEXT — Current levels vs history | Signal reliability from 30-day verification</h2>
<table>
<tr>
  <th>Factor</th>
  <th>Current</th>
  <th>1m %ile</th>
  <th>1y %ile</th>
  <th>5y %ile</th>
  <th>Regime</th>
  <th>Signal Bias (1m)</th>
  <th>Tailwind reliability</th>
  <th>Headwind reliability</th>
</tr>
{regime_rows}
</table>
</div>

{sr_table}
</body></html>'''

    # Build support/resistance table
    def sr_rows(levels, label, color):
        if not levels:
            return f'<tr><td colspan="5" style="color:#444;">No {label} zones found</td></tr>'
        rows = ''
        for idx, l in enumerate(levels):
            opacity = '1.0' if idx == 0 else '0.6'
            tag = '← on graph' if idx == 0 else ''
            rows += f'''<tr>
<td style="color:{color}; opacity:{opacity};">{label}{idx+1}</td>
<td style="opacity:{opacity};">{l["price"]:.2f}</td>
<td style="opacity:{opacity};">{l["pct_from_current"]:+.1f}%</td>
<td style="opacity:{opacity};">{l["volume"]:,}</td>
<td style="opacity:{opacity}; color:#555;">{l["date"]} {tag}</td>
</tr>'''
        return rows

    sr_table = f'''
<div class="regime-section" style="margin-top:8px;">
<h2>SUPPORT & RESISTANCE — Volume-based large circle levels (last 1 year daily)</h2>
<table>
<tr>
  <th>Level</th>
  <th>Price</th>
  <th>% from current</th>
  <th>Volume</th>
  <th>Date</th>
</tr>
{sr_rows(resistance_levels, "R", "#ff4466")}
{sr_rows(support_levels, "S", "#44ff88")}
</table>
</div>'''

    filename = f'fms_supergraph_{instrument_name.lower().replace(" ","_")}.html'
    with open(filename, 'w') as f:
        f.write(html)
    print(f"  Saved: {filename}")
    progress(4)
    return filename

# Run for Defence ETF
filename = generate_supergraph("DEFENCE_ETF", 6385665)
print(f"Open: open {filename}")
