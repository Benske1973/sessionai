from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from session_ai.pipeline import sync_symbol

UTC = timezone.utc


class FakeClient:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def fetch_1m(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        mask = (self.frame.timestamp >= start) & (self.frame.timestamp < end)
        return self.frame.loc[mask].copy()


def make_frame(start, periods):
    ts = pd.date_range(start, periods=periods, freq="1min")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 10.0,
            "turnover": 10.0,
        }
    )


def test_sync_symbol_persists_candles_sessions_and_reproducibility_state(tmp_path):
    frame = make_frame("2026-08-25T00:00:00Z", 2 * 24 * 60)
    client = FakeClient(frame)

    result = sync_symbol(
        "tut-usdt",
        tmp_path,
        days=2,
        now=datetime(2026, 8, 27, 0, 0, tzinfo=UTC),
        client=client,
        storage_format="csv",
    )

    assert result.symbol == "TUT-USDT"
    assert result.candle_count == len(frame)
    assert result.session_count > 0
    assert result.candles_path.exists()
    assert result.sessions_path.exists()
    assert (tmp_path / "TUT-USDT" / "state.json").exists()
    state = result.state
    assert state["source"] == "kucoin-spot"
    assert state["base_resolution"] == "1min"
    assert state["active_window_days"] == 2
    assert len(state["raw_data_sha256"]) == 64
    assert state["sessions"]["London"] == "07:00-16:00 UTC"
    assert client.calls == [
        (
            "TUT-USDT",
            datetime(2026, 8, 25, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 27, 0, 0, tzinfo=UTC),
        )
    ]


def test_second_sync_refetches_two_minutes_before_last_candle(tmp_path):
    initial = make_frame("2026-08-26T00:00:00Z", 60)
    first_client = FakeClient(initial)
    sync_symbol(
        "TUT-USDT",
        tmp_path,
        days=1,
        now=datetime(2026, 8, 26, 1, 0, tzinfo=UTC),
        client=first_client,
        storage_format="csv",
    )

    extended = make_frame("2026-08-26T00:00:00Z", 120)
    second_client = FakeClient(extended)
    sync_symbol(
        "TUT-USDT",
        tmp_path,
        days=1,
        now=datetime(2026, 8, 26, 2, 0, tzinfo=UTC),
        client=second_client,
        storage_format="csv",
    )

    _, start, end = second_client.calls[0]
    assert start == datetime(2026, 8, 26, 0, 57, tzinfo=UTC)
    assert end == datetime(2026, 8, 26, 2, 0, tzinfo=UTC)
