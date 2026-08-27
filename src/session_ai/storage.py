from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .kucoin import CANDLE_COLUMNS, empty_candles


def _parquet_available() -> bool:
    return importlib.util.find_spec("pyarrow") is not None or importlib.util.find_spec("fastparquet") is not None


def _canonical_candles(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return empty_candles()
    missing = set(CANDLE_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"missing candle columns: {sorted(missing)}")

    result = frame.loc[:, CANDLE_COLUMNS].copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    for column in CANDLE_COLUMNS[1:]:
        result[column] = pd.to_numeric(result[column], errors="raise").astype("float64")
    return (
        result.sort_values("timestamp", kind="stable")
        .drop_duplicates("timestamp", keep="last")
        .reset_index(drop=True)
    )


class CoinStore:
    def __init__(self, root: Path | str, symbol: str, storage_format: str = "auto") -> None:
        self.root = Path(root)
        self.symbol = symbol.upper().strip()
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if storage_format not in {"auto", "parquet", "csv"}:
            raise ValueError("storage_format must be auto, parquet, or csv")
        if storage_format == "parquet" and not _parquet_available():
            raise RuntimeError("Parquet storage requested but no pandas Parquet engine is installed")
        self.storage_format = "parquet" if storage_format == "parquet" or (storage_format == "auto" and _parquet_available()) else "csv"
        self.symbol_dir.mkdir(parents=True, exist_ok=True)

    @property
    def symbol_dir(self) -> Path:
        return self.root / self.symbol

    @property
    def candles_path(self) -> Path:
        return self.symbol_dir / f"candles_1m.{self.storage_format}"

    @property
    def sessions_path(self) -> Path:
        return self.symbol_dir / f"sessions.{self.storage_format}"

    @property
    def state_path(self) -> Path:
        return self.symbol_dir / "state.json"

    def _write_frame(self, frame: pd.DataFrame, path: Path) -> None:
        temp = path.with_name(f".{path.stem}.tmp{path.suffix}")
        if self.storage_format == "parquet":
            frame.to_parquet(temp, index=False)
        else:
            frame.to_csv(temp, index=False, date_format="%Y-%m-%dT%H:%M:%S.%fZ")
        temp.replace(path)

    def _read_frame(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        if self.storage_format == "parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    def read_candles(self) -> pd.DataFrame:
        if not self.candles_path.exists():
            return empty_candles()
        frame = self._read_frame(self.candles_path)
        return _canonical_candles(frame)

    def merge_candles(self, new: pd.DataFrame) -> pd.DataFrame:
        current = self.read_candles()
        incoming = _canonical_candles(new)
        merged = _canonical_candles(pd.concat([current, incoming], ignore_index=True))
        self._write_frame(merged, self.candles_path)
        return merged

    def write_sessions(self, frame: pd.DataFrame) -> None:
        clean = frame.copy().reset_index(drop=True)
        self._write_frame(clean, self.sessions_path)

    def read_sessions(self) -> pd.DataFrame:
        frame = self._read_frame(self.sessions_path)
        for column in ("start_ts", "end_ts"):
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], utc=True)
        return frame

    def write_state(self, payload: dict[str, Any]) -> None:
        temp = self.state_path.with_name(".state.tmp.json")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.state_path)

    def data_hash(self, frame: pd.DataFrame) -> str:
        clean = _canonical_candles(frame)
        stable = clean.copy()
        stable["timestamp"] = stable["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        payload = stable.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
