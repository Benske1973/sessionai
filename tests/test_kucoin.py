from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd
import pytest

from session_ai.kucoin import KuCoinSpotClient, iter_time_pages, normalize_legacy_candles

UTC = timezone.utc


def test_normalize_legacy_candles_sorts_oldest_first_and_maps_ohlcv():
    rows = [
        ["120", "11", "12", "13", "10", "5", "60"],
        ["60", "10", "11", "12", "9", "4", "42"],
    ]

    frame = normalize_legacy_candles(rows)

    assert frame["timestamp"].astype("int64").tolist() == [60_000_000_000, 120_000_000_000]
    assert frame.loc[0, ["open", "high", "low", "close", "volume", "turnover"]].tolist() == [
        10.0,
        12.0,
        9.0,
        11.0,
        4.0,
        42.0,
    ]


def test_iter_time_pages_is_contiguous_and_never_exceeds_limit():
    start = datetime(2026, 8, 1, tzinfo=UTC)
    end = datetime(2026, 8, 3, tzinfo=UTC)

    pages = list(iter_time_pages(start, end, max_candles=1500))

    assert pages[0][0] == start
    assert pages[-1][1] == end
    assert all((b - a) <= timedelta(minutes=1500) for a, b in pages)
    assert all(left[1] == right[0] for left, right in zip(pages, pages[1:]))


def test_iter_time_pages_rejects_naive_datetimes():
    with pytest.raises(ValueError, match="timezone-aware"):
        list(iter_time_pages(datetime(2026, 8, 1), datetime(2026, 8, 2, tzinfo=UTC)))


def test_fetch_1m_normalizes_deduplicates_and_clips_to_half_open_range():
    start = datetime(1970, 1, 1, 0, 1, tzinfo=UTC)
    end = datetime(1970, 1, 1, 0, 4, tzinfo=UTC)
    responses = [
        {
            "code": "200000",
            "data": [
                ["240", "13", "14", "15", "12", "7", "98"],
                ["180", "12", "13", "14", "11", "6", "78"],
                ["120", "11", "12", "13", "10", "5", "60"],
                ["60", "10", "11", "12", "9", "4", "42"],
                ["120", "11", "12.5", "13", "10", "5", "62.5"],
            ],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/market/candles"
        assert request.url.params["symbol"] == "TUT-USDT"
        assert request.url.params["type"] == "1min"
        return httpx.Response(200, json=responses.pop(0))

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.kucoin.test")
    client = KuCoinSpotClient(base_url="https://api.kucoin.test", http_client=http)

    frame = client.fetch_1m("tut-usdt", start, end)

    assert frame["timestamp"].tolist() == list(pd.to_datetime([60, 120, 180], unit="s", utc=True))
    assert frame.loc[frame["timestamp"] == pd.Timestamp("1970-01-01T00:02:00Z"), "close"].item() == 12.5
