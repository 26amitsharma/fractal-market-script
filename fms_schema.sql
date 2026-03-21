-- FMS Database Schema
-- All tables designed for Defence ETF focus initially
-- Extensible to any instrument

-- ============================================================
-- CONFIGURATION TABLES
-- ============================================================

-- Data sources configuration
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,          -- 'oil', 'gas', 'usd_inr', 'usd_cny'
    display_name TEXT NOT NULL,  -- 'Brent Crude Oil'
    source_type TEXT NOT NULL,   -- 'yahoo', 'investing', 'zerodha'
    source_symbol TEXT NOT NULL, -- 'BZ=F', 'NG=F', 'INR=X', 'CNY=X'
    status TEXT DEFAULT 'active',-- 'active', 'error', 'disabled'
    last_checked TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Instruments tracked
CREATE TABLE IF NOT EXISTS instruments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,        -- 'MODEFENCE'
    name TEXT NOT NULL,          -- 'Motilal Oswal Defence ETF'
    sector TEXT NOT NULL,        -- 'defence'
    exchange TEXT NOT NULL,      -- 'NSE'
    zerodha_token INTEGER,       -- 6385665
    yahoo_symbol TEXT,           -- for macro-stripped view
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sector indices
CREATE TABLE IF NOT EXISTS sector_indices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector TEXT NOT NULL,        -- 'defence'
    index_name TEXT NOT NULL,    -- 'Nifty India Defence'
    source_symbol TEXT,
    zerodha_token INTEGER,
    is_active INTEGER DEFAULT 1
);

-- ============================================================
-- MACRO DATA TABLES
-- ============================================================

-- Daily macro factor prices
CREATE TABLE IF NOT EXISTS macro_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factor TEXT NOT NULL,        -- 'oil', 'gas', 'usd_inr', 'usd_cny'
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    change_pct REAL,             -- daily % change
    is_significant INTEGER DEFAULT 0, -- 1 if top 10% movement day
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(factor, date)
);

-- Significant movement days per macro factor
CREATE TABLE IF NOT EXISTS macro_spike_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factor TEXT NOT NULL,        -- 'oil', 'gas', 'usd_inr', 'usd_cny'
    date DATE NOT NULL,
    change_pct REAL NOT NULL,    -- % change on that day
    direction TEXT NOT NULL,     -- 'up', 'down'
    percentile REAL,             -- how extreme this move was
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(factor, date)
);

-- ============================================================
-- STOCK DATA TABLES
-- ============================================================

-- Daily stock prices
CREATE TABLE IF NOT EXISTS stock_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume INTEGER,
    change_pct REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument_id, date),
    FOREIGN KEY(instrument_id) REFERENCES instruments(id)
);

-- ============================================================
-- CORRELATION TABLES
-- ============================================================

-- Stock vs macro correlation profile
CREATE TABLE IF NOT EXISTS correlation_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    factor TEXT NOT NULL,        -- 'oil', 'gas', 'usd_inr', 'usd_cny'
    correlation_score REAL,      -- -1 to +1
    follow_rate_up REAL,         -- % of macro up spikes stock followed up
    follow_rate_down REAL,       -- % of macro down spikes stock followed down
    avg_stock_move_on_spike REAL,-- avg stock % move on macro spike days
    sample_count INTEGER,        -- number of spike days analyzed
    signal_strength TEXT,        -- 'strong', 'medium', 'weak', 'noise'
    last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument_id, factor)
);

-- Individual spike day stock response
CREATE TABLE IF NOT EXISTS spike_day_response (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    factor TEXT NOT NULL,
    date DATE NOT NULL,
    macro_change_pct REAL,       -- how much macro moved
    stock_change_pct REAL,       -- how much stock moved same day
    stock_change_next_day REAL,  -- how much stock moved next day
    followed INTEGER,            -- 1 if stock followed macro direction
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument_id, factor, date)
);

-- ============================================================
-- FMS DATA TABLES
-- ============================================================

-- FMS window primitives per generation
CREATE TABLE IF NOT EXISTS fms_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    generation TEXT NOT NULL,    -- 'G1', 'G2', 'G3', 'G4'
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    x_amplitude REAL,
    y_inefficiency REAL,
    y_x_ratio REAL,
    direction TEXT,              -- 'up', 'down'
    degree_pct REAL,
    start_price REAL,
    end_price REAL,
    avg_volume REAL,
    body_count INTEGER,
    limb_count INTEGER,
    body_position TEXT,          -- 'upper', 'lower', 'mixed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument_id, generation, window_start)
);

-- FMS pattern events (large circle occurrences)
CREATE TABLE IF NOT EXISTS fms_pattern_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    generation TEXT NOT NULL,
    event_date TIMESTAMP NOT NULL,
    price REAL,
    position TEXT,               -- 'upper', 'lower'
    size_ratio REAL,
    consumption_tier TEXT,       -- '100%', '50-99%', '<50%'
    consumed_count INTEGER,
    next1_direction TEXT,
    next1_distance REAL,
    next2_direction TEXT,
    next2_distance REAL,
    both_up INTEGER,
    both_down INTEGER,
    mixed INTEGER,
    macro_flag TEXT,             -- which macro factor was spiking this day if any
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FMS signals (current state snapshots)
CREATE TABLE IF NOT EXISTS fms_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    snapshot_time TIMESTAMP NOT NULL,
    master_signal TEXT,          -- 'BULLISH', 'BEARISH', 'NEUTRAL', etc
    bull_score REAL,
    bear_score REAL,
    confidence_pct REAL,
    g1_signal TEXT,
    g2_signal TEXT,
    g3_signal TEXT,
    g4_signal TEXT,
    master_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- OUTCOME TRACKING (for tuning)
-- ============================================================

-- Track signal outcomes for weight tuning
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL,
    instrument_id INTEGER NOT NULL,
    signal_date DATE NOT NULL,
    signal_direction TEXT,       -- what FMS predicted
    price_at_signal REAL,
    price_after_1day REAL,
    price_after_1week REAL,
    price_after_1month REAL,
    outcome_1day TEXT,           -- 'correct', 'incorrect', 'neutral'
    outcome_1week TEXT,
    outcome_1month TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(signal_id) REFERENCES fms_signals(id)
);

-- ============================================================
-- SEED DATA
-- ============================================================

INSERT OR IGNORE INTO data_sources (name, display_name, source_type, source_symbol) VALUES
    ('oil',     'Brent Crude Oil',    'yahoo', 'BZ=F'),
    ('gas',     'Natural Gas',        'yahoo', 'NG=F'),
    ('usd_inr', 'USD/INR',            'yahoo', 'INR=X'),
    ('usd_cny', 'USD/CNY',            'yahoo', 'CNY=X');

INSERT OR IGNORE INTO instruments (symbol, name, sector, exchange, zerodha_token) VALUES
    ('MODEFENCE', 'Motilal Oswal Nifty India Defence ETF', 'defence', 'NSE', 6385665);

INSERT OR IGNORE INTO sector_indices (sector, index_name, zerodha_token) VALUES
    ('defence', 'Nifty India Defence', 413961);

