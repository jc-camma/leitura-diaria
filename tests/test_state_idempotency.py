from datetime import date

from app.state import PendingReadConfirmation, State, StateStore


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


def test_pending_read_confirmation_blocks_new_send() -> None:
    today = date(2026, 3, 6)
    state = State(
        last_sent_date="2026-03-05",
        last_day_index=8,
        pending_read_confirmation=PendingReadConfirmation(
            day=8,
            title="Titulo",
            sent_date="2026-03-05",
            token="abc123",
        ),
    )
    assert StateStore.can_send_on(state, today, force=False) is False


def test_pending_read_confirmation_does_not_block_when_confirmation_is_disabled() -> None:
    today = date(2026, 3, 6)
    state = State(
        last_sent_date="2026-03-05",
        last_day_index=8,
        pending_read_confirmation=PendingReadConfirmation(
            day=8,
            title="Titulo",
            sent_date="2026-03-05",
            token="abc123",
        ),
    )
    assert StateStore.can_send_on(state, today, force=False, require_confirmation=False) is True


def test_force_resends_pending_day_while_unread() -> None:
    today = date(2026, 3, 6)
    state = State(
        last_sent_date="2026-03-05",
        last_day_index=8,
        pending_read_confirmation=PendingReadConfirmation(
            day=8,
            title="Titulo",
            sent_date="2026-03-05",
            token="abc123",
        ),
    )
    day = StateStore.resolve_day_index_for_send(state, today, force=True)
    assert day == 8


def test_confirm_pending_read_releases_next_send() -> None:
    today = date(2026, 3, 6)
    state = State(
        last_sent_date="2026-03-05",
        last_day_index=8,
        pending_read_confirmation=PendingReadConfirmation(
            day=8,
            title="Titulo",
            sent_date="2026-03-05",
            token="abc123",
        ),
    )
    status = StateStore.confirm_pending_read(state, "abc123")
    assert status == "confirmed"
    assert StateStore.can_send_on(state, today, force=False) is True


def test_register_success_updates_index_to_actual_sent_day() -> None:
    state = State(last_sent_date="2026-03-10", last_day_index=27)
    updated = StateStore.register_success(
        state,
        date(2026, 3, 11),
        26,
        "Titulo",
        "manual-reset",
        tracking_token="abc123",
    )
    assert updated.last_day_index == 26
    assert updated.pending_read_confirmation is not None
    assert updated.pending_read_confirmation.day == 26


def test_additional_send_ignores_same_day_lock_after_confirmation() -> None:
    state = State(last_sent_date="2026-03-05", last_day_index=8)
    assert StateStore.can_send_additional_on(state) is True
    assert StateStore.resolve_day_index_for_additional_send(state) == 9


def test_additional_send_stays_blocked_while_current_reading_is_unread() -> None:
    state = State(
        last_sent_date="2026-03-05",
        last_day_index=8,
        pending_read_confirmation=PendingReadConfirmation(
            day=8,
            title="Titulo",
            sent_date="2026-03-05",
            token="abc123",
        ),
    )
    assert StateStore.can_send_additional_on(state) is False
