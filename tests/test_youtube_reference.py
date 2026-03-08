from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from app.lesson import Lesson
from app.youtube import find_most_relevant_video


class DummyTextResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def __enter__(self) -> "DummyTextResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def read(self) -> bytes:
        return self._text.encode("utf-8")


def _lesson() -> Lesson:
    return Lesson(
        day=1,
        title="As 48 Leis do Poder",
        author="Robert Greene",
        theme="Estrategia e influencia",
        central_idea="Ideia central",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["P1", "P2"],
        summary_bullets=["B1", "B2", "B3"],
    )


def _wrap_initial_data(initial_data: dict) -> str:
    return f"<html><script>var ytInitialData = {json.dumps(initial_data)};</script></html>"


def test_youtube_fallback_without_api_key() -> None:
    result = find_most_relevant_video(_lesson(), youtube_api_key=None)
    assert result.source == "search"
    assert result.url.startswith("https://www.youtube.com/results?")
    parsed = parse_qs(urlparse(result.url).query)
    assert parsed["search_query"][0] == "As 48 Leis do Poder Robert Greene resumo"


def test_youtube_prefers_configured_channels_in_order(monkeypatch) -> None:  # noqa: ANN001
    initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "vid-arata-high",
                                                "title": {"runs": [{"text": "Arata top"}]},
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Arata",
                                                            "navigationEndpoint": {
                                                                "browseEndpoint": {
                                                                    "canonicalBaseUrl": "/@arataacademy"
                                                                }
                                                            },
                                                        }
                                                    ]
                                                },
                                                "viewCountText": {"simpleText": "4,2 mi visualizações"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "vid-seja-low",
                                                "title": {"runs": [{"text": "Seja prioridade"}]},
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Seja",
                                                            "navigationEndpoint": {
                                                                "browseEndpoint": {
                                                                    "canonicalBaseUrl": "/@sejaumapessoamelhor"
                                                                }
                                                            },
                                                        }
                                                    ]
                                                },
                                                "viewCountText": {"simpleText": "120 mil visualizações"},
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    html = _wrap_initial_data(initial_data)

    def _fake_urlopen(url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if "youtube.com/results?" in url:
            return DummyTextResponse(html)
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr("app.youtube.urlopen", _fake_urlopen)
    result = find_most_relevant_video(_lesson(), youtube_api_key="fake-key")
    assert result.source == "search"
    assert result.url == "https://www.youtube.com/watch?v=vid-seja-low"
    assert result.title == "Seja prioridade"


def test_youtube_picks_most_viewed_inside_same_priority_channel(monkeypatch) -> None:  # noqa: ANN001
    initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "vid-seja-low",
                                                "title": {"runs": [{"text": "Seja baixo"}]},
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Seja",
                                                            "navigationEndpoint": {
                                                                "browseEndpoint": {
                                                                    "canonicalBaseUrl": "/@sejaumapessoamelhor"
                                                                }
                                                            },
                                                        }
                                                    ]
                                                },
                                                "viewCountText": {"simpleText": "25 mil visualizações"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "vid-seja-top",
                                                "title": {"runs": [{"text": "Seja topo"}]},
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Seja",
                                                            "navigationEndpoint": {
                                                                "browseEndpoint": {
                                                                    "canonicalBaseUrl": "/@sejaumapessoamelhor"
                                                                }
                                                            },
                                                        }
                                                    ]
                                                },
                                                "viewCountText": {"simpleText": "1,1 mi visualizações"},
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    html = _wrap_initial_data(initial_data)

    def _fake_urlopen(url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if "youtube.com/results?" in url:
            return DummyTextResponse(html)
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr("app.youtube.urlopen", _fake_urlopen)
    result = find_most_relevant_video(_lesson(), youtube_api_key="fake-key")
    assert result.url == "https://www.youtube.com/watch?v=vid-seja-top"
    assert result.title == "Seja topo"


def test_youtube_returns_search_results_when_no_preferred_channel(monkeypatch) -> None:  # noqa: ANN001
    initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "vid-other",
                                                "title": {"runs": [{"text": "Canal qualquer"}]},
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Outro canal",
                                                            "navigationEndpoint": {
                                                                "browseEndpoint": {
                                                                    "canonicalBaseUrl": "/@canalqqualquer"
                                                                }
                                                            },
                                                        }
                                                    ]
                                                },
                                                "viewCountText": {"simpleText": "8 mi visualizações"},
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    html = _wrap_initial_data(initial_data)

    def _fake_urlopen(url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if "youtube.com/results?" in url:
            return DummyTextResponse(html)
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr("app.youtube.urlopen", _fake_urlopen)
    result = find_most_relevant_video(_lesson(), youtube_api_key="fake-key")
    assert result.url.startswith("https://www.youtube.com/results?")
    parsed = parse_qs(urlparse(result.url).query)
    assert parsed["search_query"][0] == "As 48 Leis do Poder Robert Greene resumo"
