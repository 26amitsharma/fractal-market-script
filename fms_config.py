import sqlite3
import yfinance as yf
from datetime import datetime, timedelta

DB_PATH = 'fms.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_macro_data():
    """Fetch latest macro data from Yahoo Finance and store in DB"""
    conn = get_db()
    
    sources = conn.execute('SELECT * FROM data_sources WHERE status != ?', ('disabled',)).fetchall()
    
    results = []
    for source in sources:
        try:
            ticker = yf.Ticker(source['source_symbol'])
            hist = ticker.history(period='6mo')
            
            if hist.empty:
                conn.execute('UPDATE data_sources SET status=?, last_error=?, last_checked=? WHERE name=?',
                           ('error', 'No data returned', datetime.now(), source['name']))
                results.append((source['name'], 'ERROR', 'No data returned'))
                continue

            # Calculate daily % changes
            hist['change_pct'] = hist['Close'].pct_change() * 100

            # Find significant movement days (top 10% absolute moves)
            threshold = hist['change_pct'].abs().quantile(0.90)

            inserted = 0
            for date, row in hist.iterrows():
                if not row['change_pct'] or str(row['change_pct']) == 'nan':
                    continue

                date_str = date.strftime('%Y-%m-%d')
                is_significant = 1 if abs(row['change_pct']) >= threshold else 0

                try:
                    conn.execute('''INSERT OR IGNORE INTO macro_daily 
                        (factor, date, open, high, low, close, change_pct, is_significant)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (source['name'], date_str,
                         round(float(row['Open']), 4),
                         round(float(row['High']), 4),
                         round(float(row['Low']), 4),
                         round(float(row['Close']), 4),
                         round(float(row['change_pct']), 4),
                         is_significant))
                    inserted += 1
                except:
                    pass

                # Store spike days separately
                if is_significant:
                    direction = 'up' if row['change_pct'] > 0 else 'down'
                    try:
                        conn.execute('''INSERT OR IGNORE INTO macro_spike_days
                            (factor, date, change_pct, direction, percentile)
                            VALUES (?,?,?,?,?)''',
                            (source['name'], date_str,
                             round(float(row['change_pct']), 4),
                             direction,
                             round(float(abs(row['change_pct']) / hist['change_pct'].abs().max() * 100), 1)))
                    except:
                        pass

            conn.execute('UPDATE data_sources SET status=?, last_checked=?, last_error=NULL WHERE name=?',
                        ('active', datetime.now(), source['name']))
            conn.commit()
            results.append((source['name'], 'OK', f'{inserted} days stored'))

        except Exception as e:
            conn.execute('UPDATE data_sources SET status=?, last_error=?, last_checked=? WHERE name=?',
                        ('error', str(e), datetime.now(), source['name']))
            conn.commit()
            results.append((source['name'], 'ERROR', str(e)))

    conn.close()
    return results

def generate_config_page():
    """Generate HTML configuration page"""
    conn = get_db()

    sources = conn.execute('SELECT * FROM data_sources ORDER BY name').fetchall()
    instruments = conn.execute('SELECT * FROM instruments ORDER BY sector, symbol').fetchall()
    sectors = conn.execute('SELECT * FROM sector_indices ORDER BY sector').fetchall()

    # Macro data summary
    macro_summary = {}
    for source in sources:
        rows = conn.execute('''SELECT COUNT(*) as cnt, MIN(date) as first, MAX(date) as last,
                              COUNT(CASE WHEN is_significant=1 THEN 1 END) as spikes
                              FROM macro_daily WHERE factor=?''', (source['name'],)).fetchone()
        macro_summary[source['name']] = rows

    conn.close()

    def status_badge(status):
        color = '#4f8' if status == 'active' else '#f84' if status == 'error' else '#888'
        return f'<span style="color:{color}; font-weight:bold;">{status.upper()}</span>'

    html = f'''<!DOCTYPE html>
<html>
<head>
<title>FMS Configuration</title>
<style>
  body {{ background:#111; font-family:monospace; color:#eee; padding:20px; max-width:1000px; }}
  h1 {{ color:#4af; margin-bottom:4px; }}
  h2 {{ color:#888; font-size:13px; margin:20px 0 8px 0; border-bottom:1px solid #222; padding-bottom:4px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:20px; }}
  th {{ color:#555; font-size:11px; text-align:left; padding:6px 8px; border-bottom:1px solid #222; }}
  td {{ font-size:11px; padding:6px 8px; border-bottom:1px solid #1a1a1a; color:#aaa; }}
  .section {{ background:#161616; border:1px solid #222; border-radius:6px; padding:16px; margin-bottom:16px; }}
  .refresh-btn {{ background:#1a2a1a; border:1px solid #4f8; color:#4f8; padding:6px 14px; 
                  border-radius:4px; cursor:pointer; font-family:monospace; font-size:11px; }}
</style>
</head>
<body>
<h1>FMS Configuration</h1>
<p style="color:#555; font-size:10px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="section">
<h2>MACRO DATA SOURCES</h2>
<table>
  <tr>
    <th>Factor</th>
    <th>Display Name</th>
    <th>Source</th>
    <th>Symbol</th>
    <th>Status</th>
    <th>Data Range</th>
    <th>Total Days</th>
    <th>Spike Days</th>
    <th>Last Checked</th>
  </tr>
'''

    for s in sources:
        m = macro_summary.get(s['name'])
        data_range = f"{m['first']} → {m['last']}" if m and m['cnt'] > 0 else 'No data'
        total_days = m['cnt'] if m else 0
        spike_days = m['spikes'] if m else 0
        last_checked = s['last_checked'][:16] if s['last_checked'] else 'Never'
        last_error = f'<div style="color:#f84; font-size:10px;">{s["last_error"]}</div>' if s['last_error'] else ''

        html += f'''  <tr>
    <td style="color:#eee;">{s['name']}</td>
    <td>{s['display_name']}</td>
    <td>{s['source_type']}</td>
    <td style="color:#4af;">{s['source_symbol']}</td>
    <td>{status_badge(s['status'])}{last_error}</td>
    <td style="color:#678;">{data_range}</td>
    <td>{total_days}</td>
    <td>{spike_days}</td>
    <td style="color:#555;">{last_checked}</td>
  </tr>
'''

    html += f'''</table>
</div>

<div class="section">
<h2>TRACKED INSTRUMENTS</h2>
<table>
  <tr>
    <th>Symbol</th>
    <th>Name</th>
    <th>Sector</th>
    <th>Exchange</th>
    <th>Zerodha Token</th>
    <th>Active</th>
  </tr>
'''

    for inst in instruments:
        active = '<span style="color:#4f8;">YES</span>' if inst['is_active'] else '<span style="color:#888;">NO</span>'
        html += f'''  <tr>
    <td style="color:#eee;">{inst['symbol']}</td>
    <td>{inst['name']}</td>
    <td style="color:#4af;">{inst['sector']}</td>
    <td>{inst['exchange']}</td>
    <td style="color:#678;">{inst['zerodha_token']}</td>
    <td>{active}</td>
  </tr>
'''

    html += f'''</table>
</div>

<div class="section">
<h2>SECTOR INDICES</h2>
<table>
  <tr>
    <th>Sector</th>
    <th>Index Name</th>
    <th>Zerodha Token</th>
  </tr>
'''

    for sec in sectors:
        html += f'''  <tr>
    <td style="color:#4af;">{sec['sector']}</td>
    <td>{sec['index_name']}</td>
    <td style="color:#678;">{sec['zerodha_token']}</td>
  </tr>
'''

    html += '''</table>
</div>

</body>
</html>'''

    with open('fms_config.html', 'w') as f:
        f.write(html)
    print("Config page saved: fms_config.html")

if __name__ == '__main__':
    print("Fetching macro data...")
    results = fetch_macro_data()
    print()
    print("Macro fetch results:")
    for name, status, msg in results:
        print(f"  {name:<10} {status:<6} {msg}")
    print()
    generate_config_page()
    print("Open: open fms_config.html")
