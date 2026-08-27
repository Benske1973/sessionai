# Session AI Forecaster — Design Specification

Date: 2026-08-27
Status: Draft for user review

## 1. Goal

Build a per-coin AI research and forecasting system that downloads the most recent 30 days of 1-minute market data, reconstructs the Sydney, Tokyo, London, and New York sessions, analyzes each coin independently, learns transitions between sessions, and generates a forecast before each upcoming session.

The system must not hard-code assumptions such as “price low at session open means price rises.” It must collect objective market features and let statistical/AI models determine which relationships matter for each coin.

## 2. Primary success criterion

Before a session starts, the system produces a per-coin forecast using only information that would have been available at that exact historical time.

Example output:

- Direction probability: bullish / bearish / range
- First move probability: up first / down first
- Likely path: e.g. sweep previous low -> reversal -> midpoint
- Expected favorable excursion (MFE)
- Expected adverse excursion (MAE)
- Expected session range
- Continuation vs reversal probability
- Confidence score
- Similar historical cases and their outcomes
- Session-sequence context: whether the next session usually continues or reverses the pattern established by prior sessions

## 3. Scope of V1

V1 focuses on one exchange data source and spot USDT pairs.

Data window:
- Rolling latest 30 days for active forecasting
- Historical data is retained permanently so the system can later compare recent vs older behavior

Base resolution:
- 1-minute candles
- Higher timeframes are derived locally where useful

Sessions:
- Sydney
- Tokyo
- London
- New York

Session time definitions must be configurable and normalized to UTC internally.

## 4. Core principle: each coin is its own market

Each coin receives its own behavioral history and forecasting state.

The system must never assume that a pattern found for TUT-USDT also applies to USELESS-USDT, DOGE-USDT, or another asset.

Shared infrastructure is allowed, but pattern statistics, feature importance, sequence behavior, model state, confidence, and forecasts are stored per coin.

## 5. Data pipeline

### 5.1 Raw data

For each symbol, store 1-minute OHLCV candles:

- timestamp UTC
- open
- high
- low
- close
- volume
- turnover where available

The downloader updates incrementally rather than downloading the whole month on every run.

### 5.2 Storage layout

Recommended structure:

```text
data/
  TUT-USDT/
    candles_1m.parquet
    sessions.parquet
    forecasts.parquet
    outcomes.parquet
    ai_reports/
    state.json
  USELESS-USDT/
    ...
```

CSV import/export remains supported for manual inspection and for sending a coin dataset to ChatGPT for deeper AI review.

Parquet is preferred internally because 1-minute histories across many coins become large and repetitive.

## 6. Session reconstruction

Every 1-minute candle is assigned to its applicable session window.

For every completed session, calculate objective properties including:

- session open/high/low/close
- percentage return
- total range
- close position inside session range
- opening position relative to previous session range
- distance from previous session high/low/midpoint
- volume totals
- rolling relative volume measures
- volatility
- early-session returns (5m, 15m, 30m, 60m)
- maximum favorable excursion from session open
- maximum adverse excursion from session open
- order in which important levels were reached
- whether previous session high/low was swept
- whether a sweep reversed or continued

The full normalized 1-minute session shape is retained so shape-based models can be added.

## 7. Session transitions and sequences

The system must explicitly model transitions:

- Sydney -> Tokyo
- Tokyo -> London
- London -> New York
- New York -> Sydney

It must also model multi-session context:

- Sydney + Tokyo -> London
- Tokyo + London -> New York
- Complete daily sequences

The system should be able to discover behaviors such as:

- Tokyo establishes direction and London usually continues it
- Tokyo trends strongly but London usually mean-reverts
- Sydney and Tokyo both rise, London extends, New York often exhausts/reverses
- a previous-session liquidity sweep materially changes the next session’s likely path

These are examples only and must not be encoded as fixed rules.

## 8. Forecast-time feature snapshot

For every historical training example, create a snapshot at a precise time immediately before the target session begins.

The snapshot may include only data available before that cutoff.

Examples:

- completed prior sessions
- prior session OHLC/range/volume
- prior session normalized shape
- last 5/15/30/60-minute behavior
- distance to prior session levels
- 24-hour range position
- recent volatility
- recent volume acceleration/deceleration
- current coin-specific rolling statistics

No target-session candle or derived future information may enter this snapshot.

## 9. Anti-leakage requirements

This is mandatory.

The system must enforce temporal causality:

1. Target session data is never present in the input snapshot.
2. Train/test splits are chronological, not random.
3. Rolling calculations are shifted so they only use past observations.
4. Scalers/encoders are fit on training history only.
5. Similarity search may only search historical cases that occurred before the forecast timestamp during backtests.
6. Model evaluation is walk-forward / expanding-window or rolling-window.

Any result that violates these rules is invalid.

## 10. AI architecture

V1 uses a hybrid design rather than asking an LLM to numerically infer patterns from tens of thousands of raw rows.

### Layer A — deterministic feature engine

Python performs exact session segmentation, transformations, level calculations, normalization, outcomes, and leakage-safe snapshots.

### Layer B — machine-learning pattern engine

Use tabular ML for prediction and feature discovery. Candidate families include CatBoost, LightGBM, XGBoost, calibrated tree ensembles, and nearest-neighbor similarity models.

The first implementation should favor interpretable, robust tabular models over deep neural networks because the initial per-session sample size is small.

Separate targets include:

- direction class
- first-move class
- continuation/reversal class
- MFE regression
- MAE regression
- session-range regression
- key-level hit probabilities

### Layer C — pattern discovery

Unsupervised or similarity-based techniques identify recurring pre-session states and normalized session sequences.

Candidate approaches:

- clustering on engineered features
- nearest-neighbor retrieval
- dimensionality reduction for research visualization
- later: learned embeddings for normalized session shapes

### Layer D — AI analyst / LLM

An LLM receives structured statistics, model outputs, retrieved historical examples, feature importance, and sequence context.

Its role is to:

- explain the forecast in natural language
- identify recurring behaviors worth investigating
- compare current behavior with previous weeks
- flag behavior shifts
- propose new hypotheses for the deterministic/ML layer to test

The LLM is not the sole numerical decision engine and must not fabricate statistics.

## 11. Per-coin model strategy

Thirty days provide only around 30 examples for each specific session, so V1 must avoid pretending a highly complex model is statistically reliable.

Initial strategy:

- retain each coin independently
- use the rolling 30-day window for current relevance
- retain older data for expanding evidence
- weight recent observations more strongly where validated
- use similarity and simple calibrated models when sample size is small
- increase model complexity only after enough historical examples exist

Confidence must account for sample size and similarity density, not only raw model probability.

## 12. Forecast output schema

Each forecast record contains at least:

```json
{
  "symbol": "TUT-USDT",
  "target_session": "London",
  "forecast_timestamp": "...",
  "direction": {
    "bullish": 0.71,
    "bearish": 0.20,
    "range": 0.09
  },
  "first_move": {
    "up": 0.43,
    "down": 0.57
  },
  "continuation_probability": 0.68,
  "reversal_probability": 0.24,
  "expected_mfe_pct": 1.6,
  "expected_mae_pct": -0.5,
  "expected_range_pct": 2.3,
  "likely_path": [
    "possible previous-session low sweep",
    "reversal",
    "previous-session midpoint test"
  ],
  "confidence": 0.76,
  "similar_case_count": 11,
  "model_version": "..."
}
```

The actual values above are illustrative only.

## 13. Outcome and self-evaluation

When the target session closes, compare forecast with reality.

Record:

- actual direction
- actual first move
- actual MFE/MAE
- actual range
- levels reached and order
- continuation/reversal outcome
- probability calibration result
- forecast error
- whether the predicted path was materially correct

This creates a permanent forecast ledger.

The model is evaluated on what it predicted before the session, never by an explanation created afterward.

## 14. Behavior shift detection

For each coin, compare recent behavior against older behavior.

Track changes such as:

- feature importance shifts
- session transition probability changes
- reduced similarity to older patterns
- degradation of forecast calibration
- volatility regime shifts

Output warnings such as:

“Recent TUT London behavior no longer resembles its prior 30-day pattern; confidence reduced.”

## 15. Automation concept

A local downloader can continuously update data.

A scheduled analysis job should:

1. detect new candle data
2. update sessions
3. close/evaluate sessions that have ended
4. rebuild leakage-safe current feature snapshots
5. update or refit eligible per-coin models
6. generate forecasts before upcoming sessions
7. save structured forecasts and human-readable AI reports

Google Drive or another synchronized cloud folder may later be used as a bridge for ChatGPT-accessible CSV/report review, but the local core engine must not depend on manual uploads.

## 16. Research workflow with ChatGPT

For deep investigation, export a per-coin research package containing:

- 30-day raw 1m CSV
- session summary CSV
- transition summary CSV
- forecast/outcome history
- nearest historical matches for the current forecast
- model feature importance / SHAP-style explanation where available

This package can be uploaded to ChatGPT for independent AI review and discovery of additional hypotheses.

Any hypothesis produced by ChatGPT must then be statistically tested against the historical data before being promoted into the forecasting engine.

## 17. V1 user interface

V1 should prioritize a research dashboard rather than automated order placement.

Per coin, show:

- current price and current/next session
- next-session forecast
- direction probabilities
- first-move probabilities
- expected MFE/MAE/range
- continuation/reversal probabilities
- sequence classification
- similar historical cases
- confidence and sample size
- last forecasts vs outcomes
- behavior-shift warning

Paper trading may consume these forecasts later, but live trading is outside V1.

## 18. Logs and reproducibility

Every forecast must be reproducible.

Log:

- exact input cutoff timestamp
- raw-data version/hash
- feature-set version
- model version
- model training window
- forecast values
- outcome values
- configuration

Do not overwrite previous forecasts after observing the outcome.

## 19. Testing strategy

Mandatory tests:

- session boundary tests
- UTC/timezone conversion tests
- incremental download gap/duplicate tests
- no-future-data leakage tests
- feature calculation tests
- session transition linkage tests
- walk-forward split tests
- forecast persistence tests
- outcome scoring tests
- deterministic re-run tests

Backtests must recreate historical forecasts as they would have been generated in real time.

## 20. V1 implementation phases

Phase 1 — Data foundation
- exchange candle downloader
- rolling/permanent storage
- session segmentation
- session summaries

Phase 2 — Forecast dataset
- pre-session snapshots
- outcome targets
- sequence/transition features
- leakage tests

Phase 3 — Baseline AI
- similarity engine
- simple calibrated classifiers/regressors
- confidence logic
- per-coin reports

Phase 4 — Walk-forward evaluation
- historical forecast replay
- scoring/calibration
- model comparison

Phase 5 — AI analyst
- structured model evidence -> LLM research prompt/report
- discovered-hypothesis workflow

Phase 6 — Research dashboard and scheduler
- per-coin dashboard
- scheduled forecasts
- forecast/outcome ledger
- behavior-shift indicators

## 21. Explicit non-goals for V1

- no live automatic order execution
- no assumption that one coin’s pattern transfers to another
- no opaque confidence without sample-size evidence
- no LLM-only prediction from raw CSV
- no random train/test split
- no retrospective use of target-session information

## 22. Design decision summary

The project is a per-coin, leakage-safe, sequence-aware AI forecasting engine.

Its central unit of learning is not simply a candle and not simply a session. It is:

**coin -> prior session sequence -> pre-session state -> next session outcome**

The active model should focus on recent 30-day behavior while retaining historical evidence for validation, behavior-shift detection, and growing statistical confidence.
