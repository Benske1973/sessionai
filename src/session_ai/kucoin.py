from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator

import httpx
import pandas as pd

CANDLE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "turnover")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def empty_candles() -> pd.DataFrame:
    frame = pd.DataFrame(columns=CANDLE_COLUMNS)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for column in CANDLE_COLUMNS[1:]:
        frame[column] = frame[column].astype("float64")
    return frame


def normalize_legacy_candles(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return empty_candles()

    parsed = pd.DataFrame(
        rows,
        columns=["epoch", "open", "close", "high", "low", "volume", "turnover"],
    )
    parsed["timestamp"] = pd.to_datetime(parsed.pop("epoch").astype("int64"), unit="s", utc=True)
    for column in CANDLE_COLUMNS[1:]:
        parsed[column] = pd.to_numeric(parsed[column], errors="raise").astype("float64")

    return (
        parsed.loc[:, CANDLE_COLUMNS]
        .sort_values("timestamp", kind="stable")
        .drop_duplicates("timestamp", keep="last")
        .reset_index(drop=True)
    )


def iter_time_pages(
    start: datetime,
    end: datetime,
    max_candles: int = 1500,
) -> Iterator[tuple[datetime, datetime]]:
    _require_aware(start, "start")
    _require_aware(end, "end")
    if end <= start:
        raise ValueError("end must be after start")
    if max_candles < 1:
        raise ValueError("max_candles must be at least 1")

    page_span = timedelta(minutes=max_candles)
    cursor = start
    while cursor < end:
        page_end = min(cursor + page_span, end)
        yield cursor, page_end
        cursor = page_end


class KuCoinSpotClient:
    def __init__(
        self,
        base_url: str = "https://api.kucoin.com",
        timeout: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self.http = http_client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self.http.close()

    def __enter__(self) -> "KuCoinSpotClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch_1m(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        _require_aware(start, "start")
        _require_aware(end, "end")
        if end <= start:
            raise ValueError("end must be after start")

        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("symbol must not be empty")

        frames: list[pd.DataFrame] = []
        for page_start, page_end in iter_time_pages(start, end):
            response = self.http.get(
                "/api/v1/market/candles",
                params={
                    "symbol": symbol,
                    "type": "1min",
                    "startAt": int(page_start.timestamp()),
                    "endAt": int(page_end.timestamp()),
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "200000":
                raise RuntimeError(f"KuCoin API error: {payload.get('code')}: {payload.get('msg', '')}")
            frames.append(normalize_legacy_candles(payload.get("data") or []))

        if not frames:
            return empty_candles()

        merged = pd.concat(frames, ignore_index=True)
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        else:
            start_ts = start_ts.tz_convert("UTC")
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")
        merged = merged[(merged["timestamp"] >= start_ts) & (merged["timestamp"] < end_ts)]
        return (
            merged.sort_values("timestamp", kind="stable")
            .drop_duplicates("timestamp", keep="last")
            .reset_index(drop=True)
        )
