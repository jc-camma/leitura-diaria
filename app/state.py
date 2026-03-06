from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


MAX_HISTORY = 30


class ReadingPlanCompletedError(RuntimeError):
    """Raised when all 365 readings were already delivered."""


@dataclass
class State:
    last_sent_date: str | None = None
    last_day_index: int = 0
    sent_history: list[dict[str, Any]] = field(default_factory=list)


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> State:
        if not self.path.exists():
            return State()
        with self.path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return State(
            last_sent_date=payload.get("last_sent_date"),
            last_day_index=int(payload.get("last_day_index", 0)),
            sent_history=list(payload.get("sent_history", [])),
        )

    def save(self, state: State) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(state), fh, ensure_ascii=False, indent=2)

    @staticmethod
    def can_send_on(state: State, today: date, force: bool = False) -> bool:
        if force:
            return True
        return state.last_sent_date != today.isoformat()

    @staticmethod
    def resolve_day_index_for_send(state: State, today: date, force: bool = False) -> int:
        if state.last_sent_date == today.isoformat() and force:
            if state.last_day_index <= 0:
                return 1
            return state.last_day_index
        next_day = state.last_day_index + 1
        if next_day > 365:
            raise ReadingPlanCompletedError("As 365 leituras já foram concluídas.")
        return next_day

    @staticmethod
    def register_success(
        state: State,
        sent_date: date,
        day_index: int,
        title: str,
        mode: str,
    ) -> State:
        state.last_sent_date = sent_date.isoformat()
        state.last_day_index = max(state.last_day_index, day_index)
        state.sent_history.append(
            {
                "date": sent_date.isoformat(),
                "day": day_index,
                "title": title,
                "mode": mode,
            }
        )
        state.sent_history = state.sent_history[-MAX_HISTORY:]
        return state

