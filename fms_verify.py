from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import pytz

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
    'oil': '#ff4444', 'gas': '#ffaa00',
    'usd_inr': '#4488ff', 'usd_cny': '#44ff88'
}

def run_verification():
    print("Fetching data...")
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    hourly = kite.historical_data(6385665, from_date, to_date, '60minute')
    print(f"  Defence ETF: {len(hourly)} hourly candles")

    macro_dfs = {}
    for factor, symbol in MACRO_SOURCES.items():
        df = yf.Ticker(symbol).history(period='1mo', interval='1h')
        df['change_pct'] = df['Close'].pct_change() * 100
        df = df.dropna(subset=['change_pct'])
        threshold = df['change_pct'].abs().quantile(0.90)
        df['is_spike'] = df['change_pct'].abs() >= threshold
        df.index = pd.to_datetime(df.index, utc=True)
        macro_dfs[factor] = {'df': df, 'threshold': threshold}

    # Per factor analysis
    factor_results = {}
    for factor in MACRO_SOURCES:
        factor_results[factor] = {
            'tailwind': {'cont_1h': 0, 'rev_1h': 0, 'cont_2h': 0, 'rev_2h': 0, 'events': []},
            'headwind': {'cont_1h': 0, 'rev_1h': 0, 'cont_2h': 0, 'rev_2h': 0, 'events': []}
        }

    for i, candle in enumerate(hourly):
        if i < 1 or i >= len(hourly) - 2:
            continue

        try:
            utc = candle['date'].astimezone(pytz.utc)
            hour_str = utc.strftime('%Y-%m-%d %H')
        except:
            hour_str = candle['date'].strftime('%Y-%m-%d %H')

        curr_price = candle['close']
        prev_price = hourly[i-1]['close']
        next1_price = hourly[i+1]['close']
        next2_price = hourly[i+2]['close']
        stock_up = curr_price > prev_price

        for factor, mdata in macro_dfs.items():
            df = mdata['df']
            matching = df[df.index.strftime('%Y-%m-%d %H') == hour_str]
            if matching.empty or not matching.iloc[0]['is_spike']:
                continue

            sq_type = 'tailwind' if stock_up else 'headwind'
            data = factor_results[factor][sq_type]

            move_1h = round((next1_price - curr_price) / curr_price * 100, 3)
            move_2h = round((next2_price - curr_price) / curr_price * 100, 3)

            if stock_up:
                cont_1h = next1_price > curr_price
                cont_2h = next2_price > curr_price
            else:
                cont_1h = next1_price < curr_price
                cont_2h = next2_price < curr_price

            if cont_1h: data['cont_1h'] += 1
            else: data['rev_1h'] += 1
            if cont_2h: data['cont_2h'] += 1
            else: data['rev_2h'] += 1

            data['events'].append({
                'date': candle['date'].strftime('%m-%d %H:%M'),
                'prev': round(prev_price, 2),
                'curr': round(curr_price, 2),
                'next1': round(next1_price, 2),
                'next2': round(next2_price, 2),
                'move_1h': move_1h,
                'move_2h': move_2h,
                'cont_1h': cont_1h,
                'cont_2h': cont_2h
            })

    return factor_results

def verdict(pct):
    if pct >= 70: return 'STRONG', '#4f8'
    elif pct >= 60: return 'MODERATE', '#fa8'
    elif pct >= 45: return 'NEUTRAL', '#888'
    else: return 'REVERSAL', '#f84'

def generate_verify_html(factor_results):
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Verify — Thesis Verification</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; }}
  h1 {{ color:#4af; margin-bottom:4px; }}
  h2 {{ color:#888; font-size:13px; margin:20px 0 8px 0; border-bottom:1px solid #222; padding-bottom:4px; }}
  h3 {{ font-size:12px; margin:12px 0 6px 0; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:12px; }}
  th {{ color:#555; font-size:10px; text-align:left; padding:4px 8px; border-bottom:1px solid #222; }}
  td {{ font-size:10px; padding:3px 8px; border-bottom:1px solid #1a1a1a; color:#aaa; }}
  .section {{ background:#161616; border:1px solid #222; border-radius:6px; padding:16px; margin-bottom:16px; }}
  .summary {{ background:#1a1a2a; border:1px solid #2a2a4a; border-radius:6px; padding:16px; margin-bottom:16px; }}
</style>
</head>
<body>
<h1>FMS Verify — Macro Signal Thesis Verification</h1>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Defence ETF | Last 30 days</p>
<p style="color:#666; font-size:11px;">Thesis: After a macro spike hour, do next 1h and 2h continue in same direction?</p>

<div class="summary">
<h2>SUMMARY — Signal Reliability by Factor</h2>
<table>
<tr>
  <th>Factor</th>
  <th>Type</th>
  <th>Events</th>
  <th>1h continuation%</th>
  <th>2h continuation%</th>
  <th>1h Verdict</th>
  <th>2h Verdict</th>
  <th>Actionable?</th>
</tr>'''

    for factor in ['usd_inr', 'usd_cny', 'oil', 'gas']:
        color = MACRO_COLORS[factor]
        for sq_type in ['tailwind', 'headwind']:
            data = factor_results[factor][sq_type]
            total_1h = data['cont_1h'] + data['rev_1h']
            total_2h = data['cont_2h'] + data['rev_2h']
            if total_1h == 0:
                continue
            pct_1h = round(data['cont_1h'] / total_1h * 100, 1)
            pct_2h = round(data['cont_2h'] / total_2h * 100, 1) if total_2h > 0 else 0
            v1, c1 = verdict(pct_1h)
            v2, c2 = verdict(pct_2h)
            actionable = '✅ YES' if pct_1h >= 65 or pct_2h >= 65 else '❌ NO'
            type_color = '#4f8' if sq_type == 'tailwind' else '#f84'
            html += f'''<tr>
<td style="color:{color};">{factor}</td>
<td style="color:{type_color};">{sq_type}</td>
<td>{total_1h}</td>
<td>{pct_1h}%</td>
<td>{pct_2h}%</td>
<td style="color:{c1};">{v1}</td>
<td style="color:{c2};">{v2}</td>
<td>{actionable}</td>
</tr>'''

    html += '''</table>
</div>'''

    # Per factor detail
    for factor in ['usd_inr', 'usd_cny', 'oil', 'gas']:
        color = MACRO_COLORS[factor]
        html += f'<div class="section"><h2 style="color:{color};">{factor.upper()}</h2>'

        for sq_type in ['tailwind', 'headwind']:
            data = factor_results[factor][sq_type]
            if not data['events']:
                continue

            total = data['cont_1h'] + data['rev_1h']
            pct_1h = round(data['cont_1h'] / total * 100, 1) if total > 0 else 0
            pct_2h = round(data['cont_2h'] / total * 100, 1) if total > 0 else 0
            v1, c1 = verdict(pct_1h)
            type_color = '#4f8' if sq_type == 'tailwind' else '#f84'

            html += f'''<h3 style="color:{type_color};">{sq_type.upper()} — {total} events | 1h: {pct_1h}% <span style="color:{c1};">{v1}</span> | 2h: {pct_2h}%</h3>
<table>
<tr><th>Date</th><th>Prev</th><th>Curr</th><th>Next1</th><th>Next2</th><th>1h%</th><th>2h%</th><th>1h</th><th>2h</th></tr>'''

            for e in data['events']:
                c1h = '✓' if e['cont_1h'] else '✗'
                c2h = '✓' if e['cont_2h'] else '✗'
                col_1h = '#4f8' if e['cont_1h'] else '#f84'
                col_2h = '#4f8' if e['cont_2h'] else '#f84'
                m1 = f"+{e['move_1h']}%" if e['move_1h'] >= 0 else f"{e['move_1h']}%"
                m2 = f"+{e['move_2h']}%" if e['move_2h'] >= 0 else f"{e['move_2h']}%"
                html += f'''<tr>
<td>{e["date"]}</td><td>{e["prev"]}</td><td>{e["curr"]}</td>
<td>{e["next1"]}</td><td>{e["next2"]}</td>
<td>{m1}</td><td>{m2}</td>
<td style="color:{col_1h};">{c1h}</td>
<td style="color:{col_2h};">{c2h}</td>
</tr>'''
            html += '</table>'

        html += '</div>'

    html += '</body></html>'

    with open('fms_verify.html', 'w') as f:
        f.write(html)
    print("Saved: fms_verify.html")

factor_results = run_verification()
generate_verify_html(factor_results)
print("Open: open fms_verify.html")
