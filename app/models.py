from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookEntry:
    day: int
    title: str
    author: str
    theme: str
    key_ideas: list[str]
    practical_applications: list[str]
    reflection_question: str
    category: str | None = None
    optional_quote: str | None = None


@dataclass(frozen=True)
class Lesson:
    day: int
    title: str
    author: str
    theme: str
    central_idea: str
    concepts: list[str]
    practical_applications: list[str]
    reflection_question: str
    guided_reading: list[str]
    summary_bullets: list[str]
    optional_quote: str | None = None

    def word_count(self) -> int:
        text_parts: list[str] = [
            self.central_idea,
            self.reflection_question,
            *self.concepts,
            *self.practical_applications,
            *self.guided_reading,
            *(self.summary_bullets or []),
        ]
        if self.optional_quote:
            text_parts.append(self.optional_quote)
        return sum(len(part.split()) for part in text_parts)

