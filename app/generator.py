from __future__ import annotations

from app.lesson import BookEntry, Lesson, generate_first_draft


def generate_draft(entry: BookEntry) -> Lesson:
    return generate_first_draft(entry)
