# Fractal Market Script (FMS)

## Vision

FMS is an original market intelligence system built on the principle that financial markets are recursive, self-similar systems. Price action generates a natural language of shapes across multiple timeframes. This language is not defined by humans—it is discovered by the system from data. The role of the architect is to define principles and guidance only.

FMS does not predict price. It measures structural alignment across generations of market data and translates that into probability-weighted intelligence.

---

## Core Philosophy

**Markets are fractal.** The same patterns that appear in a 30-minute window also appear in a 6-week window and a 1.4-year window. When these patterns align across scales simultaneously, that is your highest conviction signal.

**Intelligence flows bottom-up.** The parent (larger timeframe) is a passive crystallized memory of what children (smaller timeframes) have repeatedly done. Children write. Parents store. No top-down influence.

**Compression is intelligence.** A weekly candle has compressed 1950 minutes of market behavior into one data point. Everything random has been averaged out. Only sustained, dominant forces survive to shape that candle.

---

## The 1:30 Rule

The foundational discovery: 30 samples at any interval produces a natural shape completion.

- 1 minute x 30 = 30 minutes (G1)
- 15 minutes x 30 = 7.5 hours (G2)
- 1 day x 30 = 6 weeks (G3)
- 1 week x 30 = 7.5 months (G4)

This reflects natural human decision cycles embedded in market behavior. Supported by Central Limit Theorem.

---

## Storage Primitives

Every 30-sample window is characterized by two numbers:

X = Amplitude. Maximum distance from lowest low to highest high.
Y = Inefficiency. Extra steps beyond the shortest path diagonal.
Y/X Ratio = inefficiency score. Higher = more noise. Lower = cleaner trend.

These two numbers are scale-invariant and directly comparable across all four generations.

---

## The Maze Walk

Each 30-sample window is a journey through a hidden maze. Intelligence lives in how those 30 steps unfold. Start and end points define the diagonal. Wall breaks are unusually large jumps. Tortoise walk means patient accumulation. Path complexity measures deviation from diagonal.

---

## Circle Character Language

Each candle is represented as a circle:
- Circle size = volume normalized within generation
- Circle position = close price relative to center line
- Warm color = high volume body circle
- Cool color = low volume limb circle
- Consumption score = smaller circles absorbed within radius

Consumption tiers:
- 100% = all nearby circles absorbed = maximum dominance
- 50-99% = partial absorption
- less than 50% = weak absorption

---

## Four Generation Architecture

G1: 1min x 30 = 30 minutes (red/warm)
G2: 15min x 30 = 7.5 hours (amber/yellow)
G3: 1day x 30 = 6 weeks (teal/cyan)
G4: 1week x 30 = 7.5 months (blue/cool)

Generational weights: G4=40%, G3=28%, G2=20%, G1=12%

Parent lifecycle: Children repeat, pattern crystallizes, parent forms, new children confirm or challenge, parent strengthens or dissolves.

---

## Visual Dashboard

Per generation row: 3 consecutive windows on common price scale, body trail, color theme, volume scaling, signal panel below.

Zoom-in flow: G4 current to G3 body to G2 body to G1 body to G1 current.

Master summary: weighted signal, human readable summary, bull/bear score with confidence.

---

## Two Pool Intelligence System

Pool 1 - Natural Laws (universal):
- G3 lower half + consumption less than 50% = +18.6% excess bullish STRONG (Defence ETF)
- G3 upper half + consumption less than 50% = -18.0% excess bearish STRONG (Defence ETF)
- G4 lower + consumption 50-99% = +26.2% excess bullish, 0% both-down STRONG (SunPharma)
- G4 upper + consumption less than 50% = -46.5% excess bearish, 0% both-up STRONG (SunPharma)

Pool 2 - Observed Behaviors: instrument-specific, grows over time, self-improving.

---

## Signal Scoring

For each generation: find large circles, classify position and consumption tier, match against pattern database, count bullish vs bearish occurrences.

Master signal = weighted sum across generations.
Bull score vs Bear score gives direction.
Confidence = dominant score divided by total score.

---

## Self-Similarity Score (Pending - Phase 3)

Three components:
1. Direction alignment (weight 0.4)
2. Y/X ratio similarity (weight 0.3)
3. Body position pattern similarity (weight 0.3)

Per generation pair: G4-G3, G3-G2, G2-G1.
Overall fractal resonance score: 0-100%.

---

## Utility Layer (Pending - Phase 3)

Actionable intelligence on top of FMS signals:
- Watchlist tracking for specific stocks
- Entry/exit zone identification
- Alert system when FMS signal crosses threshold
- Cross-stock comparison within sector

---

## Project Structure

app.py - Flask backend, Zerodha auth, API endpoints
fms_local.py - Local analysis, visual dashboard generation
fms_dashboard.py - Unified dashboard, graphs + signals + master summary
fms_patterns.py - Pattern capture engine, historical signal analysis
fms_signal.py - Signal layer, current state analysis
fms_dashboard.html - Unified dashboard output
requirements.txt - Python dependencies
Procfile - Render deployment config
README.md - This file

---

## Tech Stack

Language: Python 3.14
Data: Zerodha Kite Connect API
Backend: Flask + Gunicorn
Hosting: Render.com
Version control: GitHub
Key libraries: kiteconnect, flask

---

## Instruments

Defence ETF: MODEFENCE token 6385665 - primary instrument
SunPharma: token 857857 - used for pattern validation

---

## Data Limits

Zerodha historical limit: 2000 days
Weekly candles available: approximately 285 from September 2020
G4 pattern sample sizes: 34-43 events

---

## Key Insights

1. G4 is most predictive - weekly candles carry maximum crystallized intelligence
2. Upper half large circles at G3/G4 = local tops - statistically confirmed
3. Lower half large circles at G3/G4 = launchpad - statistically confirmed
4. Consumption score matters - 100% absorption signals are strongest
5. Per-instrument patterns differ - Defence ETF and SunPharma behave differently
6. Price zone and pattern are separate intelligence layers

---

## Development Log

Phase 1 Complete: Live data pipeline, X/Y primitives, 4-generation comparison
Phase 2 Section 1 Complete: Visual dashboard, circle language, body trails, zoom-in flow
Phase 2 Section 2 Complete: Pattern capture engine, two-pool system, unified dashboard
Phase 3 Pending: Self-similarity score, SQLite storage, utility layer, alerts

---

## Philosophy Note

FMS is built on the belief that markets speak a fractal language. Every weight, threshold, and baseline is temporary scaffolding. The data will eventually replace all seeds with statistically discovered truth. The system is designed to get smarter over time through honest observation and feedback.
