# Session AI Forecaster

Phase 1 is the data foundation for a per-coin, sequence-aware AI session forecaster.
It downloads KuCoin Spot 1-minute candles, keeps a permanent incremental history,
and reconstructs Sydney, Tokyo, London and New York session summaries in UTC.

This phase does **not** generate trading signals yet. Its job is to create the clean,
reproducible and leakage-safe historical dataset that the AI forecasting layer will learn from.

## Default sessions (UTC)

- Sydney: 21:00-06:00
- Tokyo: 00:00-09:00
- London: 07:00-16:00
- New York: 13:00-22:00

Sessions are independent and may overlap. Missing 1-minute bars are not invented.

## Install

```bash
python -m pip install -e .[test]
```

Parquet is preferred for long histories. Install the optional backend:

```bash
python -m pip install -e .[parquet]
```

Without a Parquet engine the project automatically uses CSV storage, which is useful
in restricted/offline environments.

## Download and build sessions

```bash
python -m session_ai sync TUT-USDT --days 30 --data-dir data
```

The first run requests the selected lookback. Later runs only fetch from two minutes
before the last stored candle through the current time, then merge by timestamp.

Output is stored per coin:

```text
data/
  TUT-USDT/
    candles_1m.parquet   # or candles_1m.csv fallback
    sessions.parquet     # or sessions.csv fallback
    state.json
```

`state.json` records the exact raw-data hash, timestamps, session definitions and counts
needed to reproduce later AI forecasts.

## Run tests

```bash
python -m pytest -q
```

## Current scope

- KuCoin Spot
- USDT pairs
- 1-minute base candles
- incremental local history
- deterministic session summaries
- no order execution
- no AI prediction yet (forecast dataset and AI models are Phase 2/3)
