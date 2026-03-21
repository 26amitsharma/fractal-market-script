import sqlite3
import yfinance as yf
from datetime import datetime, timedelta

DB_PATH = 'fms.db'

MACRO_SOURCES = {
    'oil':     'BZ=F',
    'gas':     'NG=F',
    'usd_inr': 'INR=X',
    'usd_cny': 'CNY=X'
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_macro_historical():
    conn = get_db()
    print("Loading 5 years of macro data into SQLite...")
    print()

    for factor, symbol in MACRO_SOURCES.items():
        print(f"Fetching {factor} ({symbol})...")
        try:
            df = yf.Ticker(symbol).history(period='5y')
            df['change_pct'] = df['Close'].pct_change() * 100
            df = df.dropna(subset=['change_pct'])

            # Calculate threshold for significant days
            threshold = df['change_pct'].abs().quantile(0.90)

            inserted = 0
            skipped = 0
            for date, row in df.iterrows():
                date_str = date.strftime('%Y-%m-%d')
                change = round(float(row['change_pct']), 4)
                is_significant = 1 if abs(change) >= threshold else 0

                try:
                    conn.execute('''INSERT OR IGNORE INTO macro_daily
                        (factor, date, open, high, low, close, change_pct, is_significant)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (factor, date_str,
                         round(float(row['Open']), 4),
                         round(float(row['High']), 4),
                         round(float(row['Low']), 4),
                         round(float(row['Close']), 4),
                         change, is_significant))
                    inserted += 1
                except:
                    skipped += 1

            # Store spike days
            spike_df = df[df['change_pct'].abs() >= threshold]
            spikes_inserted = 0
            for date, row in spike_df.iterrows():
                date_str = date.strftime('%Y-%m-%d')
                direction = 'up' if row['change_pct'] > 0 else 'down'
                percentile = round(float(abs(row['change_pct']) / df['change_pct'].abs().max() * 100), 1)
                try:
                    conn.execute('''INSERT OR IGNORE INTO macro_spike_days
                        (factor, date, change_pct, direction, percentile)
                        VALUES (?,?,?,?,?)''',
                        (factor, date_str,
                         round(float(row['change_pct']), 4),
                         direction, percentile))
                    spikes_inserted += 1
                except:
                    pass

            conn.commit()

            # Calculate percentile stats
            current_price = round(float(df['Close'].iloc[-1]), 4)
            high_5y = round(float(df['High'].max()), 4)
            low_5y = round(float(df['Low'].min()), 4)
            high_1y = round(float(df['High'].tail(252).max()), 4)
            low_1y = round(float(df['Low'].tail(252).min()), 4)
            high_1m = round(float(df['High'].tail(21).max()), 4)
            low_1m = round(float(df['Low'].tail(21).min()), 4)

            # Percentile of current price in 5y range
            range_5y = high_5y - low_5y
            pct_5y = round((current_price - low_5y) / range_5y * 100, 1) if range_5y > 0 else 50
            range_1y = high_1y - low_1y
            pct_1y = round((current_price - low_1y) / range_1y * 100, 1) if range_1y > 0 else 50

            print(f"  ✓ {inserted} days loaded | {spikes_inserted} spike days")
            print(f"  Current: {current_price} | 5y range: {low_5y}-{high_5y} | Percentile 5y: {pct_5y}% | 1y: {pct_1y}%")
            print(f"  Monthly high: {high_1m} | Monthly low: {low_1m}")
            print()

            # Update data source status
            conn.execute('''UPDATE data_sources SET status=?, last_checked=?, last_error=NULL
                           WHERE name=?''', ('active', datetime.now(), factor))
            conn.commit()

        except Exception as e:
            print(f"  ERROR: {e}")
            conn.execute('''UPDATE data_sources SET status=?, last_error=?, last_checked=?
                           WHERE name=?''', ('error', str(e), datetime.now(), factor))
            conn.commit()

    conn.close()

def print_regime_summary():
    """Print current regime context for all 4 factors"""
    conn = get_db()
    print("=" * 65)
    print("MACRO REGIME CONTEXT (current levels vs history)")
    print("=" * 65)

    for factor in MACRO_SOURCES:
        rows = conn.execute('''SELECT date, close, change_pct FROM macro_daily
                              WHERE factor=? ORDER BY date DESC LIMIT 252''',
                           (factor,)).fetchall()

        if not rows:
            continue

        current = rows[0]['close']
        closes_1y = [r['close'] for r in rows]
        high_1y = max(closes_1y)
        low_1y = min(closes_1y)
        range_1y = high_1y - low_1y
        pct_1y = round((current - low_1y) / range_1y * 100, 1) if range_1y > 0 else 50

        all_rows = conn.execute('''SELECT close FROM macro_daily
                                  WHERE factor=? ORDER BY date''',
                               (factor,)).fetchall()
        all_closes = [r['close'] for r in all_rows]
        high_5y = max(all_closes)
        low_5y = min(all_closes)
        range_5y = high_5y - low_5y
        pct_5y = round((current - low_5y) / range_5y * 100, 1) if range_5y > 0 else 50

        # Distance from highs
        dist_from_1y_high = round((high_1y - current) / high_1y * 100, 1)
        dist_from_5y_high = round((high_5y - current) / high_5y * 100, 1)

        # Regime label
        if pct_1y >= 80:
            regime = "ELEVATED"
            regime_color = "HIGH"
        elif pct_1y >= 50:
            regime = "NEUTRAL-HIGH"
            regime_color = "MED"
        elif pct_1y >= 20:
            regime = "NEUTRAL-LOW"
            regime_color = "MED"
        else:
            regime = "DEPRESSED"
            regime_color = "LOW"

        print(f"{factor.upper():<12} Current={current:<8} "
              f"1y_pct={pct_1y}% 5y_pct={pct_5y}% "
              f"Dist_from_1y_high={dist_from_1y_high}% "
              f"Regime={regime}")

    print("=" * 65)
    conn.close()

# Run
load_macro_historical()
print_regime_summary()
