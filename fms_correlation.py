import sqlite3
from kiteconnect import KiteConnect
from datetime import datetime, timedelta

DB_PATH = 'fms.db'
api_key = "tsm9w570sr8un8kj"
access_token = "Ika9gOlRs1KUm3bnJhEEKUVjCr4Fqcc7"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_stock_daily(instrument_id, zerodha_token):
    """Fetch and store 6 months of daily stock data"""
    conn = get_db()
    to_date = datetime.now()
    from_date = to_date - timedelta(days=180)
    
    try:
        candles = kite.historical_data(zerodha_token, from_date, to_date, 'day')
        inserted = 0
        for c in candles:
            date_str = c['date'].strftime('%Y-%m-%d')
            try:
                conn.execute('''INSERT OR IGNORE INTO stock_daily
                    (instrument_id, date, open, high, low, close, volume, change_pct)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (instrument_id, date_str,
                     c['open'], c['high'], c['low'], c['close'], c['volume'],
                     None))
                inserted += 1
            except:
                pass

        # Calculate % changes
        rows = conn.execute('''SELECT id, date, close FROM stock_daily 
                              WHERE instrument_id=? ORDER BY date''', 
                           (instrument_id,)).fetchall()
        for i in range(1, len(rows)):
            prev_close = rows[i-1]['close']
            curr_close = rows[i]['close']
            if prev_close and prev_close > 0:
                chg = round((curr_close - prev_close) / prev_close * 100, 4)
                conn.execute('UPDATE stock_daily SET change_pct=? WHERE id=?',
                           (chg, rows[i]['id']))

        conn.commit()
        print(f"  Stock data: {inserted} days stored")
        return True
    except Exception as e:
        print(f"  Error fetching stock data: {e}")
        return False
    finally:
        conn.close()

def calculate_correlation(instrument_id, factor):
    """Calculate correlation between macro factor spike days and stock movement"""
    conn = get_db()
    
    # Get spike days for this factor
    spike_days = conn.execute('''SELECT date, change_pct, direction 
                                FROM macro_spike_days 
                                WHERE factor=? 
                                ORDER BY date''', (factor,)).fetchall()
    
    if not spike_days:
        conn.close()
        return None
    
    results = []
    followed_count = 0
    
    for spike in spike_days:
        # Get stock movement on same day
        stock_day = conn.execute('''SELECT change_pct FROM stock_daily 
                                   WHERE instrument_id=? AND date=?''',
                                (instrument_id, spike['date'])).fetchone()
        
        # Get next day stock movement
        next_day = conn.execute('''SELECT change_pct FROM stock_daily 
                                  WHERE instrument_id=? AND date > ? 
                                  ORDER BY date LIMIT 1''',
                               (instrument_id, spike['date'])).fetchone()
        
        if not stock_day or stock_day['change_pct'] is None:
            continue
        
        stock_chg = stock_day['change_pct']
        next_chg = next_day['change_pct'] if next_day else None
        
        # Did stock follow macro direction?
        macro_up = spike['direction'] == 'up'
        stock_up = stock_chg > 0
        followed = 1 if macro_up == stock_up else 0
        followed_count += followed
        
        results.append({
            'date': spike['date'],
            'macro_chg': spike['change_pct'],
            'stock_chg': stock_chg,
            'next_day_chg': next_chg,
            'followed': followed
        })
        
        # Store individual spike day response
        try:
            conn.execute('''INSERT OR REPLACE INTO spike_day_response
                (instrument_id, factor, date, macro_change_pct, stock_change_pct,
                 stock_change_next_day, followed)
                VALUES (?,?,?,?,?,?,?)''',
                (instrument_id, factor, spike['date'],
                 spike['change_pct'], stock_chg, next_chg, followed))
        except:
            pass
    
    if not results:
        conn.close()
        return None
    
    count = len(results)
    follow_rate = round(followed_count / count * 100, 1)
    
    # Up follow rate
    up_spikes = [r for r in results if r['macro_chg'] > 0]
    up_follow = sum(1 for r in up_spikes if r['stock_chg'] > 0)
    follow_rate_up = round(up_follow / len(up_spikes) * 100, 1) if up_spikes else 0
    
    # Down follow rate
    dn_spikes = [r for r in results if r['macro_chg'] < 0]
    dn_follow = sum(1 for r in dn_spikes if r['stock_chg'] < 0)
    follow_rate_down = round(dn_follow / len(dn_spikes) * 100, 1) if dn_spikes else 0
    
    # Average stock move on spike days
    avg_stock_move = round(sum(abs(r['stock_chg']) for r in results) / count, 2)
    
    # Overall correlation score (-1 to +1)
    # Based on directional follow rate: 50% = 0, 100% = +1, 0% = -1
    correlation_score = round((follow_rate - 50) / 50, 3)
    
    # Signal strength
    if abs(follow_rate - 50) >= 25:
        strength = 'strong'
    elif abs(follow_rate - 50) >= 15:
        strength = 'medium'
    else:
        strength = 'weak' if abs(follow_rate - 50) >= 8 else 'noise'
    
    # Store correlation profile
    conn.execute('''INSERT OR REPLACE INTO correlation_profile
        (instrument_id, factor, correlation_score, follow_rate_up, follow_rate_down,
         avg_stock_move_on_spike, sample_count, signal_strength, last_updated)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (instrument_id, factor, correlation_score, follow_rate_up, follow_rate_down,
         avg_stock_move, count, strength, datetime.now()))
    
    conn.commit()
    conn.close()
    
    return {
        'factor': factor,
        'correlation_score': correlation_score,
        'follow_rate': follow_rate,
        'follow_rate_up': follow_rate_up,
        'follow_rate_down': follow_rate_down,
        'avg_stock_move': avg_stock_move,
        'sample_count': count,
        'strength': strength,
        'details': results
    }

def generate_correlation_report():
    """Generate HTML correlation report"""
    conn = get_db()
    
    instruments = conn.execute('SELECT * FROM instruments WHERE is_active=1').fetchall()
    
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Correlation Report</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; max-width:1100px; }}
  h1 {{ color:#4af; margin-bottom:4px; }}
  h2 {{ color:#888; font-size:13px; margin:20px 0 8px 0; border-bottom:1px solid #222; padding-bottom:4px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:16px; }}
  th {{ color:#555; font-size:11px; text-align:left; padding:6px 8px; border-bottom:1px solid #222; }}
  td {{ font-size:11px; padding:6px 8px; border-bottom:1px solid #1a1a1a; color:#aaa; }}
  .section {{ background:#161616; border:1px solid #222; border-radius:6px; padding:16px; margin-bottom:16px; }}
  .spike-table {{ font-size:10px; }}
  .spike-table td {{ padding:3px 6px; }}
</style>
</head>
<body>
<h1>FMS Correlation Report</h1>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
'''
    
    for inst in instruments:
        html += f'<div class="section"><h2>{inst["symbol"]} — {inst["name"]}</h2>'
        
        profiles = conn.execute('''SELECT * FROM correlation_profile 
                                  WHERE instrument_id=? ORDER BY ABS(correlation_score) DESC''',
                               (inst['id'],)).fetchall()
        
        if not profiles:
            html += '<p style="color:#555;">No correlation data yet.</p></div>'
            continue
        
        html += '''<table>
<tr>
  <th>Macro Factor</th>
  <th>Correlation Score</th>
  <th>Overall Follow%</th>
  <th>Up Spike Follow%</th>
  <th>Down Spike Follow%</th>
  <th>Avg Stock Move</th>
  <th>Sample Days</th>
  <th>Signal Strength</th>
</tr>'''
        
        for p in profiles:
            score = p['correlation_score']
            score_color = '#4f8' if score > 0.2 else '#f84' if score < -0.2 else '#888'
            follow_pct = round((score * 50) + 50, 1)
            
            strength_color = {'strong': '#4f8', 'medium': '#fa8', 
                             'weak': '#888', 'noise': '#444'}.get(p['signal_strength'], '#888')
            
            html += f'''<tr>
  <td style="color:#eee;">{p["factor"]}</td>
  <td style="color:{score_color}; font-weight:bold;">{score:+.3f}</td>
  <td>{follow_pct}%</td>
  <td style="color:#4f8;">{p["follow_rate_up"]}%</td>
  <td style="color:#f84;">{p["follow_rate_down"]}%</td>
  <td>{p["avg_stock_move_on_spike"]}%</td>
  <td>{p["sample_count"]}</td>
  <td style="color:{strength_color};">{p["signal_strength"].upper()}</td>
</tr>'''
        
        html += '</table>'
        
        # Spike day details per factor
        for p in profiles:
            spike_details = conn.execute('''SELECT * FROM spike_day_response 
                                          WHERE instrument_id=? AND factor=?
                                          ORDER BY date DESC LIMIT 15''',
                                        (inst['id'], p['factor'])).fetchall()
            
            if not spike_details:
                continue
            
            html += f'<h2>{p["factor"].upper()} spike days detail (last 15)</h2>'
            html += '''<table class="spike-table">
<tr>
  <th>Date</th>
  <th>Macro Move</th>
  <th>Stock Same Day</th>
  <th>Stock Next Day</th>
  <th>Followed?</th>
</tr>'''
            
            for d in spike_details:
                followed_color = '#4f8' if d['followed'] else '#f84'
                followed_text = 'YES' if d['followed'] else 'NO'
                macro_color = '#4f8' if d['macro_change_pct'] > 0 else '#f84'
                stock_color = '#4f8' if d['stock_change_pct'] and d['stock_change_pct'] > 0 else '#f84'
                next_color = '#4f8' if d['stock_change_next_day'] and d['stock_change_next_day'] > 0 else '#f84'
                next_val = f"{d['stock_change_next_day']:+.2f}%" if d['stock_change_next_day'] else 'N/A'
                
                html += f'''<tr>
  <td>{d["date"]}</td>
  <td style="color:{macro_color};">{d["macro_change_pct"]:+.2f}%</td>
  <td style="color:{stock_color};">{d["stock_change_pct"]:+.2f}%</td>
  <td style="color:{next_color};">{next_val}</td>
  <td style="color:{followed_color}; font-weight:bold;">{followed_text}</td>
</tr>'''
            
            html += '</table>'
        
        html += '</div>'
    
    html += '</body></html>'
    conn.close()
    
    with open('fms_correlation.html', 'w') as f:
        f.write(html)
    print("Correlation report saved: fms_correlation.html")

# Run
print("Fetching stock data for tracked instruments...")
conn = get_db()
instruments = conn.execute('SELECT * FROM instruments WHERE is_active=1').fetchall()
conn.close()

for inst in instruments:
    print(f"\nProcessing {inst['symbol']}...")
    fetch_stock_daily(inst['id'], inst['zerodha_token'])
    
    print("Calculating correlations:")
    for factor in ['oil', 'gas', 'usd_inr', 'usd_cny']:
        result = calculate_correlation(inst['id'], factor)
        if result:
            print(f"  {factor:<10} score={result['correlation_score']:+.3f} "
                  f"follow={result['follow_rate']}% "
                  f"strength={result['strength']}")
        else:
            print(f"  {factor:<10} insufficient data")

generate_correlation_report()
print("\nOpen: open fms_correlation.html")
