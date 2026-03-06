from datetime import date

from app.state import State, StateStore


def test_idempotency_same_day_without_force() -> None:
    today = date(2026, 3, 5)
    state = State(last_sent_date=today.isoformat(), last_day_index=8)
    assert StateStore.can_send_on(state, today, force=False) is False


def test_force_same_day_resends_same_index() -> None:
    today = date(2026, 3, 5)
    state = State(last_sent_date=today.isoformat(), last_day_index=8)
    day = StateStore.resolve_day_index_for_send(state, today, force=True)
    assert day == 8


def test_next_day_when_new_date() -> None:
    today = date(2026, 3, 5)
    state = State(last_sent_date="2026-03-04", last_day_index=8)
    day = StateStore.resolve_day_index_for_send(state, today, force=False)
    assert day == 9

