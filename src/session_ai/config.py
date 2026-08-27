from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True, slots=True)
class SessionDefinition:
    name: str
    start: time
    end: time

    @property
    def crosses_midnight(self) -> bool:
        return self.end <= self.start

    def as_text(self) -> str:
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')} UTC"


DEFAULT_SESSIONS: tuple[SessionDefinition, ...] = (
    SessionDefinition("Sydney", time(21, 0), time(6, 0)),
    SessionDefinition("Tokyo", time(0, 0), time(9, 0)),
    SessionDefinition("London", time(7, 0), time(16, 0)),
    SessionDefinition("New York", time(13, 0), time(22, 0)),
)
