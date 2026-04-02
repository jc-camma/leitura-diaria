from __future__ import annotations

from datetime import date
from pathlib import Path

from app.read_feedback import build_read_confirmation_url, confirm_latest_pending_read, confirm_read_from_token
from app.state import State, StateStore


def test_build_read_confirmation_url_appends_token() -> None:
    url = build_read_confirmation_url("https://example.com/leitura", "abc123")
    assert url == "https://example.com/leitura/confirm-read?token=abc123"


def test_confirm_read_from_token_updates_state_file(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)
    state = State()
    state = store.register_success(state, date(2026, 3, 5), 4, "Titulo", "auto", tracking_token="abc123")
    store.save(state)

    status, pending = confirm_read_from_token(state_file, "abc123")
    reloaded = store.load()

    assert status == "confirmed"
    assert pending is not None
    assert reloaded.pending_read_confirmation is not None
    assert reloaded.pending_read_confirmation.read_at is not None


def test_confirm_latest_pending_read_marks_current_lesson(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)
    state = State()
    state = store.register_success(state, date(2026, 3, 5), 7, "Titulo", "auto", tracking_token="abc123")
    store.save(state)

    status, pending = confirm_latest_pending_read(state_file)

    assert status == "confirmed"
    assert pending is not None
    assert pending.day == 7
