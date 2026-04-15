from __future__ import annotations

from datetime import date
from pathlib import Path

from app.read_feedback import (
    build_read_confirmation_url,
    build_send_next_reading_url,
    confirm_latest_pending_read,
    confirm_read_from_token,
    send_next_reading_from_token,
)
from app.state import State, StateStore


def test_build_read_confirmation_url_appends_token() -> None:
    url = build_read_confirmation_url("https://example.com/leitura", "abc123")
    assert url == "https://example.com/leitura/confirm-read?token=abc123"


def test_build_send_next_reading_url_appends_token() -> None:
    url = build_send_next_reading_url("https://example.com/leitura", "abc123")
    assert url == "https://example.com/leitura/send-next-reading?token=abc123"


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


def test_send_next_reading_from_token_confirms_current_and_sends_next(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)
    state = State()
    state = store.register_success(state, date(2026, 3, 5), 7, "Titulo 7", "auto", tracking_token="abc123")
    store.save(state)

    def _fake_deliver(state_file_arg: Path, state_arg: State, day_to_send: int):  # noqa: ANN001
        assert state_file_arg == state_file
        assert day_to_send == 8
        updated = store.load()
        updated = store.register_success(updated, date(2026, 3, 5), 8, "Titulo 8", "extra", tracking_token="tok8")
        store.save(updated)
        return updated.pending_read_confirmation

    monkeypatch.setattr("app.read_feedback._deliver_next_reading", _fake_deliver)

    status, pending = send_next_reading_from_token(state_file, "abc123")
    reloaded = store.load()

    assert status == "sent"
    assert pending is not None
    assert pending.day == 8
    assert reloaded.last_day_index == 8
    assert reloaded.pending_read_confirmation is not None
    assert reloaded.pending_read_confirmation.day == 8
