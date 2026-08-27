import pandas as pd
import pytest

from session_ai.sessions import summarize_sessions


def minute_frame(start, periods, values=None):
    ts = pd.date_range(start, periods=periods, freq="1min", tz="UTC")
    close = list(values) if values is not None else [100.0] * periods
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": close,
            "high": [x + 1 for x in close],
            "low": [x - 1 for x in close],
            "close": close,
            "volume": [1.0] * periods,
            "turnover": close,
        }
    )


def test_sydney_crosses_midnight_and_london_tokyo_overlap_is_preserved():
    candles = minute_frame("2026-08-01T00:00:00Z", 24 * 60 * 2)

    sessions = summarize_sessions("TUT-USDT", candles)

    sydney = sessions[(sessions.session_name == "Sydney") & (sessions.start_ts == pd.Timestamp("2026-08-01T21:00:00Z"))].iloc[0]
    assert sydney.end_ts == pd.Timestamp("2026-08-02T06:00:00Z")

    tokyo = sessions[(sessions.session_name == "Tokyo") & (sessions.start_ts == pd.Timestamp("2026-08-01T00:00:00Z"))].iloc[0]
    london = sessions[(sessions.session_name == "London") & (sessions.start_ts == pd.Timestamp("2026-08-01T07:00:00Z"))].iloc[0]
    assert tokyo.end_ts > london.start_ts
    assert tokyo.candle_count == 540
    assert london.candle_count == 540


def test_summary_uses_first_open_last_close_and_true_extremes():
    candles = minute_frame(
        "2026-08-01T00:00:00Z",
        9 * 60,
        values=range(100, 100 + 9 * 60),
    )

    tokyo = summarize_sessions("TUT-USDT", candles).query("session_name == 'Tokyo'").iloc[0]

    assert tokyo.open == 100
    assert tokyo.close == 639
    assert tokyo.high == 640
    assert tokyo.low == 99
    assert tokyo.return_pct == pytest.approx(539.0)
    assert tokyo.range_pct == pytest.approx((640 / 99 - 1) * 100)
    assert tokyo.close_position == pytest.approx((639 - 99) / (640 - 99))
    assert tokyo.volume == 540.0
    assert tokyo.candle_count == 540
    assert tokyo.expected_minutes == 540
    assert tokyo.coverage_pct == 100.0


def test_partial_leading_or_trailing_session_is_excluded():
    leading_partial = minute_frame("2026-08-01T00:05:00Z", 535)
    trailing_partial = minute_frame("2026-08-01T00:00:00Z", 539)

    leading = summarize_sessions("TUT-USDT", leading_partial)
    trailing = summarize_sessions("TUT-USDT", trailing_partial)

    assert not (leading.session_name == "Tokyo").any()
    assert not (trailing.session_name == "Tokyo").any()


def test_sparse_session_reports_coverage_without_fabricating_missing_minutes():
    full = minute_frame("2026-08-01T00:00:00Z", 540)
    sparse = full.drop(index=range(0, 540, 2)).reset_index(drop=True)
    before_session = minute_frame("2026-07-31T23:59:00Z", 1)
    sparse = pd.concat([before_session, sparse], ignore_index=True).sort_values("timestamp")

    tokyo = summarize_sessions("TUT-USDT", sparse).query("session_name == 'Tokyo'").iloc[0]

    assert tokyo.candle_count == 270
    assert tokyo.expected_minutes == 540
    assert tokyo.coverage_pct == pytest.approx(50.0)
