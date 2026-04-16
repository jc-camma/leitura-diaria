from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.models import BookEntry

logger = logging.getLogger(__name__)

_DEFAULT_AREAS = [
    "Lideranca e gestao",
    "Estrategia e decisao",
    "Economia e negocios",
    "Psicologia e comportamento",
    "Filosofia",
    "Historia",
    "Geopolitica",
    "Ciencia e tecnologia",
    "Sociologia",
    "Ficcao classica e contemporanea",
]

_CATALOG_PROMPT_TEMPLATE = """
Voce vai montar uma lista anual de leitura com os livros mais relevantes em cada area.

Ano de referencia: {year}
Areas obrigatorias:
{areas_list}

Regras:
- gere exatamente 15 livros por area
- cada livro precisa ter: title, author, theme
- temas devem ser claros e academicos (sem marketing)
- inclua obras classicas e contemporaneas relevantes
- evite repeticoes dentro da mesma area
- nao inclua explicacoes fora do JSON

Formato de saida (JSON puro):
{{
  "areas": [
    {{
      "area": "Nome da area",
      "books": [
        {{
          "title": "Titulo",
          "author": "Autor",
          "theme": "Tema central"
        }}
      ]
    }}
  ]
}}
""".strip()


@dataclass(frozen=True)
class CatalogBook:
    title: str
    author: str
    theme: str


@dataclass(frozen=True)
class AreaCatalog:
    area: str
    books: list[CatalogBook]


@dataclass(frozen=True)
class YearlyCatalog:
    year: int
    generated_at: str
    areas: list[AreaCatalog]


def catalog_file_for_year(data_dir: Path, year: int) -> Path:
    return data_dir / f"books_catalog_{year}.json"


def ensure_catalog_for_year(
    *,
    data_dir: Path,
    year: int,
    openai_api_key: str | None,
    openai_model: str,
    rebuild: bool = False,
) -> Path:
    catalog_path = catalog_file_for_year(data_dir, year)
    if catalog_path.exists() and not rebuild:
        return catalog_path
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY ausente. Nao foi possivel gerar o catalogo anual de livros relevantes.")

    catalog = _generate_catalog_with_openai(
        year=year,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
    )
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(_serialize_catalog(catalog), encoding="utf-8")
    logger.info("Catalogo anual salvo: %s", catalog_path)
    return catalog_path


def load_catalog(path: Path) -> YearlyCatalog:
    payload = json.loads(path.read_text(encoding="utf-8"))
    year = int(payload["year"])
    generated_at = str(payload["generated_at"])
    areas_payload = payload.get("areas", [])
    areas: list[AreaCatalog] = []
    for area_payload in areas_payload:
        area_name = str(area_payload.get("area", "")).strip()
        books_payload = area_payload.get("books", [])
        books: list[CatalogBook] = []
        for item in books_payload:
            title = str(item.get("title", "")).strip()
            author = str(item.get("author", "")).strip()
            theme = str(item.get("theme", "")).strip()
            if not (title and author and theme):
                continue
            books.append(CatalogBook(title=title, author=author, theme=theme))
        if area_name and books:
            areas.append(AreaCatalog(area=area_name, books=books))
    if not areas:
        raise RuntimeError("Catalogo anual invalido: nenhuma area valida encontrada.")
    return YearlyCatalog(year=year, generated_at=generated_at, areas=areas)


def build_year_plan(catalog: YearlyCatalog, days: int = 365) -> list[BookEntry]:
    if days < 1:
        raise ValueError("days precisa ser >= 1")
    areas = [area for area in catalog.areas if area.books]
    if not areas:
        raise RuntimeError("Catalogo sem livros para montar o plano.")

    rng = random.Random(catalog.year)
    by_area: list[list[CatalogBook]] = []
    for area in areas:
        books = list(area.books)
        rng.shuffle(books)
        by_area.append(books)
    area_offsets = [0 for _ in areas]

    plan: list[BookEntry] = []
    for day in range(1, days + 1):
        area_index = (day - 1) % len(areas)
        area = areas[area_index]
        books = by_area[area_index]
        book = books[area_offsets[area_index] % len(books)]
        area_offsets[area_index] += 1
        plan.append(
            BookEntry(
                day=day,
                title=book.title,
                author=book.author,
                theme=book.theme,
                key_ideas=_default_key_ideas(book.theme, area.area),
                practical_applications=_default_practical_applications(book.theme, area.area),
                reflection_question=_default_reflection_question(book.theme, area.area),
                category=area.area,
                optional_quote=None,
            )
        )
    return plan


def get_entry_for_day(plan: list[BookEntry], day: int) -> BookEntry:
    if day < 1 or day > len(plan):
        raise ValueError(f"Dia precisa estar entre 1 e {len(plan)}.")
    return plan[day - 1]


def _generate_catalog_with_openai(*, year: int, openai_api_key: str, openai_model: str) -> YearlyCatalog:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"SDK OpenAI indisponivel para gerar catalogo anual: {exc}") from exc

    client = OpenAI(api_key=openai_api_key.strip())
    areas_list = "\n".join([f"- {area}" for area in _DEFAULT_AREAS])
    prompt = _CATALOG_PROMPT_TEMPLATE.format(year=year, areas_list=areas_list)
    response = client.chat.completions.create(
        model=(openai_model or "gpt-4.1").strip(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": "You are an academic reading curator writing in Brazilian Portuguese."},
            {"role": "user", "content": prompt},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("OpenAI retornou catalogo anual vazio.")

    payload = json.loads(_extract_json(content))
    raw_areas = payload.get("areas", [])
    areas: list[AreaCatalog] = []
    for area_payload in raw_areas:
        area_name = str(area_payload.get("area", "")).strip()
        raw_books = area_payload.get("books", [])
        books: list[CatalogBook] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_books:
            title = str(item.get("title", "")).strip()
            author = str(item.get("author", "")).strip()
            theme = str(item.get("theme", "")).strip()
            key = (title.lower(), author.lower())
            if not (title and author and theme):
                continue
            if key in seen:
                continue
            seen.add(key)
            books.append(CatalogBook(title=title, author=author, theme=theme))
        if area_name and books:
            areas.append(AreaCatalog(area=area_name, books=books))
    if not areas:
        raise RuntimeError("OpenAI nao retornou areas validas para o catalogo anual.")
    return YearlyCatalog(
        year=year,
        generated_at=datetime.now(timezone.utc).isoformat(),
        areas=areas,
    )


def _extract_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _serialize_catalog(catalog: YearlyCatalog) -> str:
    payload = {
        "year": catalog.year,
        "generated_at": catalog.generated_at,
        "areas": [
            {
                "area": area.area,
                "books": [{"title": book.title, "author": book.author, "theme": book.theme} for book in area.books],
            }
            for area in catalog.areas
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _default_key_ideas(theme: str, area: str) -> list[str]:
    return [
        f"A obra examina {theme} sob a perspectiva de {area}.",
        "O autor organiza argumentos em torno de mecanismo, contexto e implicacoes.",
        "A leitura valoriza analise critica, comparacao historica e clareza conceitual.",
        "A tese principal depende da relacao entre causas, incentivos e limites.",
        "A principal licao e converter entendimento teorico em criterio pratico.",
    ]


def _default_practical_applications(theme: str, area: str) -> list[str]:
    return [
        f"Aplicar a lente de {theme} em uma decisao real da semana.",
        "Registrar quais premissas do autor se confirmam ou falham no seu contexto.",
        f"Construir um pequeno experimento de 7 dias usando conceitos de {area}.",
    ]


def _default_reflection_question(theme: str, area: str) -> str:
    return f"Que decisao atual fica mais clara quando voce analisa {theme} com a lente de {area}?"

