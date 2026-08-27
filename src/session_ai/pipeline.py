from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from .config import DEFAULT_SESSIONS
from .kucoin import KuCoinSpotClient
from .sessions import summarize_sessions
from .storage import CoinStore

UTC = timezone.utc


class CandleClient(Protocol):
    def fetch_1m(self, symbol: str, start: datetime, end: datetime): ...


@dataclass(frozen=True, slots=True)
class SyncResult:
    symbol: str
    candle_count: int
    session_count: int
    candles_path: Path
    sessions_path: Path
    state_path: Path
    state: dict[str, object]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(UTC)


def _iso_utc(value) -> str | None:
    if value is None:
        return None
    stamp = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    return _aware_utc(stamp).isoformat().replace("+00:00", "Z")


def sync_symbol(
    symbol: str,
    root: Path | str,
    days: int = 30,
    now: datetime | None = None,
    client: CandleClient | None = None,
    storage_format: str = "auto",
) -> SyncResult:
    if days < 1:
        raise ValueError("days must be at least 1")
    symbol = symbol.upper().strip()
    if not symbol.endswith("-USDT"):
        raise ValueError("V1 supports KuCoin spot USDT pairs only")

    now_utc = _aware_utc(now or datetime.now(UTC))
    store = CoinStore(root, symbol, storage_format=storage_format)
    existing = store.read_candles()
    if existing.empty:
        start = now_utc - timedelta(days=days)
    else:
        last = existing["timestamp"].iloc[-1].to_pydatetime()
        start = _aware_utc(last) - timedelta(minutes=2)

    owns_client = client is None
    active_client: CandleClient = client or KuCoinSpotClient()
    try:
        incoming = active_client.fetch_1m(symbol, start, now_utc)
    finally:
        if owns_client and isinstance(active_client, KuCoinSpotClient):
            active_client.close()

    candles = store.merge_candles(incoming)
    sessions = summarize_sessions(symbol, candles)
    store.write_sessions(sessions)

    first_candle = candles["timestamp"].iloc[0] if not candles.empty else None
    last_candle = candles["timestamp"].iloc[-1] if not candles.empty else None
    state: dict[str, object] = {
        "symbol": symbol,
        "source": "kucoin-spot",
        "base_resolution": "1min",
        "active_window_days": days,
        "storage_format": store.storage_format,
        "first_candle": _iso_utc(first_candle),
        "last_candle": _iso_utc(last_candle),
        "candle_count": int(len(candles)),
        "session_count": int(len(sessions)),
        "raw_data_sha256": store.data_hash(candles),
        "updated_at": _iso_utc(now_utc),
        "sessions": {definition.name: definition.as_text() for definition in DEFAULT_SESSIONS},
    }
    store.write_state(state)

    return SyncResult(
        symbol=symbol,
        candle_count=len(candles),
        session_count=len(sessions),
        candles_path=store.candles_path,
        sessions_path=store.sessions_path,
        state_path=store.state_path,
        state=state,
    )
