# Codex Handoff — Session AI Forecaster V1

## Execution mode

Use the highest available Codex model and highest practical reasoning setting. Work autonomously. Do not ask the user to review intermediate implementation details. Use the existing design spec as authoritative scope and continue until the V1 is implemented, tested, pushed, and a pull request is ready.

Repository: `Benske1973/sessionai`
Base branch: `main`
Working branch: `v1-ai-forecaster`

## Verified current repository state

`main` contains Phase 1 and commit `7abd7736e134492dcd03cc2757693f675290f43d`.
At handoff time, `v1-ai-forecaster` is identical to `main` and therefore contains no V1 AI additions yet.

Do not assume previously described local V1 code exists. Rebuild V1 from the repository, the design specification, and the requirements below.

Primary spec:
`docs/superpowers/specs/2026-08-27-session-ai-forecaster-design.md`

## Product goal

Build a per-coin Session AI Forecaster for KuCoin spot USDT markets. For each coin, use historical 1-minute data and the coin's own behavior to forecast the next Sydney, Tokyo, London, or New York session before that session starts.

The system must learn each coin independently. Never assume TUT, USELESS, DOGE, BTC, or another coin reacts to the same factors.

The forecast should be sequence-aware: what Sydney did can affect Tokyo, what Tokyo did can affect London, and what Tokyo + London did can affect New York. It must learn continuation and reversal relationships from historical data rather than hard-coding them.

## Non-negotiable anti-leakage rule

A forecast for a session may use only data actually available at the forecast cutoff.

This matters for overlapping sessions. Example: London may start while Tokyo is still active. The London forecast may use Tokyo-so-far up to the London cutoff, but never the remaining Tokyo candles or any London candle.

Historical replay must recreate exactly what would have been known in real time.

## Build all remaining V1 phases

### Phase 2 — Forecast dataset

Create leakage-safe pre-session snapshots and outcomes per coin/session.

Features should include useful objective state such as:
- completed prior-session OHLC, return, range, volume, close position
- current overlapping-session state up to the exact cutoff
- last 5m / 15m / 30m / 60m returns and ranges
- 24h position/range context
- distances to previous session high/low/midpoint
- previous session direction and sequence context
- volume and volatility context
- normalized session/price shape vectors suitable for similarity search

Targets should include at least:
- direction: bullish / bearish / range
- first_move: up / down
- session return
- MFE
- MAE
- session range
- continuation / reversal
- previous high hit
- previous low hit
- high-first / low-first where meaningful

Add strict tests proving no target-session candle enters a snapshot.

### Phase 3 — Baseline AI

Build a per-coin, per-target-session forecasting engine.

Start with a robust hybrid:
1. nearest-neighbor / similarity forecasting for small sample sizes
2. interpretable tabular ML once sufficient history exists
3. automatic fallback to similarity when a fitted model would create false confidence

Use available Python ML libraries such as scikit-learn. More complex models such as LightGBM/CatBoost/XGBoost may be evaluated but are not required unless walk-forward testing shows a real benefit.

Forecast outputs should include:
- bullish / bearish / range probabilities
- first move probabilities
- continuation / reversal probabilities
- expected MFE / MAE / range
- confidence adjusted for sample size and similarity density
- similar historical examples
- likely path summary based on measured evidence, never invented statistics

### Phase 4 — Walk-forward evaluation

Implement chronological walk-forward replay.

Never use random train/test splits.
Each historical forecast may train/search only on earlier examples.

Report useful metrics such as:
- direction accuracy / balanced accuracy
- first-move accuracy
- Brier score or probability calibration metrics
- MFE/MAE/range errors
- sample counts by coin and session
- model vs similarity baseline comparisons

The backtest must reflect how the engine would actually have run live.

### Phase 5 — AI analyst / reports

Generate structured per-coin reports from real model evidence.

The reporting layer should explain:
- next-session forecast
- most relevant current features
- similar historical cases
- continuation/reversal sequence context
- forecast confidence and why confidence is high/low
- recent behavior shift versus older behavior

Do not fabricate numerical explanations. Every number in a report must trace to stored data/model output.

Prepare a research export that can be uploaded to ChatGPT/LLM analysis:
- 30d 1m CSV
- session summaries
- transition summaries
- forecast/outcome ledger
- nearest historical matches
- model explanations/feature importance where available

### Phase 6 — Automation and local dashboard

Build CLI workflows for at least:
- `sync <symbol>`
- `universe`
- `forecast <symbol>`
- `backtest <symbol>`
- `cycle` for one autonomous analysis iteration
- `watch` for repeated local execution
- `serve` for a local research dashboard if practical

`--all-usdt` / universe mode must rediscover the KuCoin spot USDT universe periodically so newly listed coins are picked up without restarting a long-running watch process.

A cycle should isolate errors per coin: one bad symbol must not stop the entire universe.

Persist immutable forecast records. When a target session later closes, score the prior forecast against the real outcome; do not overwrite the original forecast.

## Data policy

Use a rolling recent 30-day window for current behavioral relevance, while preserving older accumulated history so sample size can grow and behavior shifts can be measured.

Keep coin models and statistics separate.

Prefer Parquet internally when available, but keep a safe CSV fallback so the application still works on environments without `pyarrow`.

## Testing requirements

Use test-driven development.

The completed V1 must include regression tests for at least:
- KuCoin pagination/deduplication
- UTC/session boundaries
- Sydney crossing midnight
- overlapping sessions
- incomplete session coverage
- pre-session snapshot anti-leakage
- transition linkage
- shape normalization
- chronological walk-forward behavior
- similarity search using only past cases
- ML fallback with insufficient samples
- forecast persistence / immutability
- outcome scoring
- deterministic reruns
- all-USDT universe refresh in watch mode
- per-coin error isolation
- end-to-end synthetic flow: data -> sessions -> training dataset -> forecast -> session close -> outcome score

Run the complete test suite before considering work complete.

## GitHub completion requirements

1. Work on `v1-ai-forecaster` or a fresh feature branch based on current `main`.
2. Keep commits coherent.
3. Add GitHub Actions CI for supported Python version(s) and `pytest`.
4. Push all implementation.
5. Open a PR to `main` summarizing architecture, tests, known limitations, and real verification output.
6. Inspect CI. Fix failures autonomously.
7. Do not merge automatically unless repository/user policy explicitly permits it; leave a green PR ready if in doubt.

## Safety / scope

This V1 is research and forecasting software. Do not add live automated order execution.
Paper-trading integration may be prepared as an interface but live orders are out of scope.

## Definition of done

V1 is done only when:
- historical KuCoin data can be transformed into per-coin leakage-safe training examples
- sequence-aware AI forecasts can be generated before sessions
- historical walk-forward performance can be measured
- forecasts are persisted and later scored against actual sessions
- all-USDT autonomous mode can discover new coins
- a user can inspect forecasts/results from CLI or a local dashboard
- tests and CI are green
- the V1 PR is open and ready for review/merge
