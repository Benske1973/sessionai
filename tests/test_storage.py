import json

import pandas as pd

from session_ai.storage import CoinStore


def candle_frame(times, closes):
    ts = pd.to_datetime(times, utc=True)
    values = [float(x) for x in closes]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "volume": [1.0] * len(ts),
            "turnover": values,
        }
    )


def test_merge_candles_deduplicates_timestamp_and_keeps_newest(tmp_path):
    store = CoinStore(tmp_path, "tut-usdt", storage_format="csv")
    store.merge_candles(
        candle_frame(["2026-08-01T00:00Z", "2026-08-01T00:01Z"], [1.0, 2.0])
    )

    merged = store.merge_candles(
        candle_frame(["2026-08-01T00:01Z", "2026-08-01T00:02Z"], [2.5, 3.0])
    )

    assert store.symbol == "TUT-USDT"
    assert merged["close"].tolist() == [1.0, 2.5, 3.0]
    assert merged["timestamp"].is_monotonic_increasing
    assert store.candles_path.name == "candles_1m.csv"
    assert store.read_candles()["close"].tolist() == [1.0, 2.5, 3.0]


def test_data_hash_is_deterministic_for_same_canonical_rows(tmp_path):
    store = CoinStore(tmp_path, "TUT-USDT", storage_format="csv")
    frame = candle_frame(["2026-08-01T00:00Z", "2026-08-01T00:01Z"], [1.0, 2.0])
    reordered = frame.iloc[::-1].reset_index(drop=True)

    assert store.data_hash(frame) == store.data_hash(reordered)


def test_write_state_is_sorted_json_and_preserves_payload(tmp_path):
    store = CoinStore(tmp_path, "TUT-USDT", storage_format="csv")

    store.write_state({"z": 1, "a": "value"})

    text = store.state_path.read_text(encoding="utf-8")
    assert text.index('"a"') < text.index('"z"')
    assert json.loads(text) == {"a": "value", "z": 1}
