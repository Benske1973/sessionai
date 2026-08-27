from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Iterator

import pandas as pd

from .config import DEFAULT_SESSIONS, SessionDefinition

UTC = timezone.utc
SESSION_COLUMNS = (
    "symbol",
    "session_name",
    "start_ts",
    "end_ts",
    "open",
    "high",
    "low",
    "close",
    "return_pct",
    "range_pct",
    "close_position",
    "volume",
    "turnover",
    "candle_count",
    "expected_minutes",
    "coverage_pct",
)


@dataclass(frozen=True, slots=True)
class SessionWindow:
    name: str
    start: datetime
    end: datetime


def _as_utc_datetime(value: datetime | pd.Timestamp) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError("session window bounds must be timezone-aware")
    return stamp.tz_convert("UTC").to_pydatetime()


def _date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def session_windows(
    start: datetime,
    end: datetime,
    definitions: tuple[SessionDefinition, ...] = DEFAULT_SESSIONS,
) -> Iterator[SessionWindow]:
    start_utc = _as_utc_datetime(start)
    end_utc = _as_utc_datetime(end)
    if end_utc <= start_utc:
        raise ValueError("end must be after start")

    first_anchor = (start_utc - timedelta(days=1)).date()
    last_anchor = end_utc.date()
    windows: list[SessionWindow] = []
    for anchor in _date_range(first_anchor, last_anchor):
        for definition in definitions:
            window_start = datetime.combine(anchor, definition.start, tzinfo=UTC)
            end_date = anchor + timedelta(days=1) if definition.crosses_midnight else anchor
            window_end = datetime.combine(end_date, definition.end, tzinfo=UTC)
            if window_end > start_utc and window_start < end_utc:
                windows.append(SessionWindow(definition.name, window_start, window_end))

    yield from sorted(windows, key=lambda item: (item.start, item.end, item.name))


def _empty_sessions() -> pd.DataFrame:
    return pd.DataFrame(columns=SESSION_COLUMNS)


def summarize_sessions(
    symbol: str,
    candles: pd.DataFrame,
    definitions: tuple[SessionDefinition, ...] = DEFAULT_SESSIONS,
) -> pd.DataFrame:
    if candles.empty:
        return _empty_sessions()
    required = {"timestamp", "open", "high", "low", "close", "volume", "turnover"}
    missing = required - set(candles.columns)
    if missing:
        raise ValueError(f"missing candle columns: {sorted(missing)}")

    frame = candles.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp", kind="stable").drop_duplicates("timestamp", keep="last")
    observable_start = frame["timestamp"].min()
    observable_end = frame["timestamp"].max() + pd.Timedelta(minutes=1)
    symbol = symbol.upper().strip()

    records: list[dict[str, object]] = []
    for window in session_windows(observable_start.to_pydatetime(), observable_end.to_pydatetime(), definitions):
        start_ts = pd.Timestamp(window.start)
        end_ts = pd.Timestamp(window.end)
        if start_ts < observable_start or end_ts > observable_end:
            continue

        part = frame[(frame["timestamp"] >= start_ts) & (frame["timestamp"] < end_ts)]
        if part.empty:
            continue

        session_open = float(part.iloc[0]["open"])
        session_close = float(part.iloc[-1]["close"])
        session_high = float(part["high"].max())
        session_low = float(part["low"].min())
        return_pct = (session_close / session_open - 1.0) * 100.0 if session_open != 0 else float("nan")
        range_pct = (session_high / session_low - 1.0) * 100.0 if session_low != 0 else float("nan")
        close_position = (
            (session_close - session_low) / (session_high - session_low)
            if session_high != session_low
            else 0.5
        )
        expected_minutes = int((end_ts - start_ts).total_seconds() // 60)
        candle_count = int(len(part))
        records.append(
            {
                "symbol": symbol,
                "session_name": window.name,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "open": session_open,
                "high": session_high,
                "low": session_low,
                "close": session_close,
                "return_pct": return_pct,
                "range_pct": range_pct,
                "close_position": close_position,
                "volume": float(part["volume"].sum()),
                "turnover": float(part["turnover"].sum()),
                "candle_count": candle_count,
                "expected_minutes": expected_minutes,
                "coverage_pct": candle_count / expected_minutes * 100.0,
            }
        )

    if not records:
        return _empty_sessions()
    result = pd.DataFrame.from_records(records, columns=SESSION_COLUMNS)
    return result.sort_values(["start_ts", "session_name"], kind="stable").reset_index(drop=True)
