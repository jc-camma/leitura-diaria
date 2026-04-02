from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


MAX_HISTORY = 30


class ReadingPlanCompletedError(RuntimeError):
    """Raised when all 365 readings were already delivered."""


@dataclass
class PendingReadConfirmation:
    day: int
    title: str
    sent_date: str
    token: str
    read_at: str | None = None


@dataclass
class State:
    last_sent_date: str | None = None
    last_day_index: int = 0
    sent_history: list[dict[str, Any]] = field(default_factory=list)
    pending_read_confirmation: PendingReadConfirmation | None = None


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> State:
        if not self.path.exists():
            return State()
        with self.path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        pending_payload = payload.get("pending_read_confirmation")
        return State(
            last_sent_date=payload.get("last_sent_date"),
            last_day_index=int(payload.get("last_day_index", 0)),
            sent_history=list(payload.get("sent_history", [])),
            pending_read_confirmation=self._load_pending_confirmation(pending_payload),
        )

    def save(self, state: State) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(state), fh, ensure_ascii=False, indent=2)

    @staticmethod
    def can_send_on(state: State, today: date, force: bool = False) -> bool:
        if force:
            return True
        if StateStore.has_pending_read_confirmation(state):
            return False
        return state.last_sent_date != today.isoformat()

    @staticmethod
    def resolve_day_index_for_send(state: State, today: date, force: bool = False) -> int:
        pending = state.pending_read_confirmation
        if force and pending is not None and pending.read_at is None:
            return pending.day
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
        tracking_token: str | None = None,
    ) -> State:
        state.last_sent_date = sent_date.isoformat()
        state.last_day_index = day_index
        state.pending_read_confirmation = PendingReadConfirmation(
            day=day_index,
            title=title,
            sent_date=sent_date.isoformat(),
            token=tracking_token or StateStore.get_tracking_token_for_lesson(state, day_index),
        )
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

    @staticmethod
    def has_pending_read_confirmation(state: State) -> bool:
        pending = state.pending_read_confirmation
        return pending is not None and pending.read_at is None

    @staticmethod
    def block_reason(state: State, today: date, force: bool = False) -> str | None:
        if force:
            return None
        pending = state.pending_read_confirmation
        if pending is not None and pending.read_at is None:
            return f"Envio bloqueado: a leitura do Dia {pending.day} ainda nao foi confirmada como lida."
        if state.last_sent_date == today.isoformat():
            return "Licao de hoje ja foi enviada; use --force para reenviar."
        return None

    @staticmethod
    def get_tracking_token_for_lesson(state: State, day_index: int) -> str:
        pending = state.pending_read_confirmation
        if pending is not None and pending.day == day_index and pending.read_at is None:
            return pending.token
        return uuid4().hex

    @staticmethod
    def confirm_pending_read(
        state: State,
        token: str,
        read_at: datetime | None = None,
    ) -> str:
        pending = state.pending_read_confirmation
        if pending is None or pending.token != token:
            return "invalid"
        if pending.read_at is not None:
            return "already_confirmed"
        pending.read_at = (read_at or datetime.now(timezone.utc)).isoformat()
        return "confirmed"

    @staticmethod
    def confirm_latest_pending_read(state: State, read_at: datetime | None = None) -> str:
        pending = state.pending_read_confirmation
        if pending is None:
            return "missing"
        if pending.read_at is not None:
            return "already_confirmed"
        pending.read_at = (read_at or datetime.now(timezone.utc)).isoformat()
        return "confirmed"

    @staticmethod
    def _load_pending_confirmation(payload: Any) -> PendingReadConfirmation | None:
        if not isinstance(payload, dict):
            return None
        token = str(payload.get("token", "")).strip()
        if not token:
            return None
        return PendingReadConfirmation(
            day=int(payload.get("day", 0)),
            title=str(payload.get("title", "")).strip(),
            sent_date=str(payload.get("sent_date", "")).strip(),
            token=token,
            read_at=str(payload.get("read_at")).strip() if payload.get("read_at") else None,
        )
