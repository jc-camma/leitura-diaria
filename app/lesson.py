from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookEntry:
    day: int
    title: str
    author: str
    theme: str
    key_ideas: list[str]
    practical_applications: list[str]
    reflection_question: str
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


def load_books(path: Path) -> list[BookEntry]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    books = [BookEntry(**item) for item in payload]
    if len(books) != 365:
        raise ValueError("books_365.json precisa conter exatamente 365 itens.")

    days = {item.day for item in books}
    expected_days = set(range(1, 366))
    if days != expected_days:
        raise ValueError("books_365.json precisa ter dias de 1 a 365 sem lacunas.")
    return sorted(books, key=lambda item: item.day)


def get_entry_for_day(books: list[BookEntry], day: int) -> BookEntry:
    if day < 1 or day > 365:
        raise ValueError("Dia precisa estar entre 1 e 365.")
    return books[day - 1]


def build_lesson(
    entry: BookEntry,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4o-mini",
) -> Lesson:
    base = _build_base_lesson(entry)
    if not openai_api_key:
        return base
    refined = _try_refine_with_openai(base, openai_api_key, openai_model)
    if refined is None:
        return base
    if refined.word_count() > 1600:
        logger.warning("Refino da IA excedeu 1600 palavras; mantendo versão base.")
        return base
    return refined


def _build_base_lesson(entry: BookEntry) -> Lesson:
    ideas = _ensure_length(entry.key_ideas, 5, "Conceito essencial")
    applications = _ensure_length(
        entry.practical_applications, 3, "Aplicação prática recomendada"
    )
    concepts = [f"{idx}. {idea}" for idx, idea in enumerate(ideas[:5], start=1)]
    practical = [f"{idx}. {app}" for idx, app in enumerate(applications[:3], start=1)]
    guided_reading = _build_guided_reading(entry, ideas, applications)
    summary = [
        f"Foco do dia: {entry.theme}.",
        f"Conceito-chave: {ideas[0]}.",
        f"Ação imediata: {applications[0]}.",
    ]
    central = (
        f"A leitura de hoje conecta o livro \"{entry.title}\" ao tema \"{entry.theme}\" "
        "com foco em decisões de gestão aplicáveis na rotina profissional. A ideia central "
        "é transformar princípios em comportamento observável: em vez de consumir teoria de "
        "forma passiva, você vai identificar sinais práticos, comparar alternativas e escolher "
        "um pequeno experimento para a semana. Esse formato acelera aprendizado porque cria "
        "repetição deliberada: você lê, interpreta, testa e revisa. Ao final, o objetivo não "
        "é apenas concordar com o autor, mas converter o conteúdo em clareza de prioridades, "
        "melhor comunicação com o time e disciplina para executar o que realmente gera resultado."
    )

    lesson = Lesson(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        central_idea=central,
        concepts=concepts,
        practical_applications=practical,
        reflection_question=entry.reflection_question.strip(),
        guided_reading=guided_reading,
        summary_bullets=summary,
        optional_quote=entry.optional_quote.strip() if entry.optional_quote else None,
    )

    return _ensure_target_word_count(lesson)


def _build_guided_reading(
    entry: BookEntry,
    ideas: list[str],
    applications: list[str],
) -> list[str]:
    paragraphs: list[str] = []
    paragraphs.append(
        f"No contexto de \"{entry.title}\", {entry.author} mostra que resultados sustentáveis "
        f"dependem de coerência entre intenção e método. O tema \"{entry.theme}\" não deve ser "
        "tratado como slogan, mas como um sistema de escolhas diárias: o que priorizar, o que "
        "eliminar e como medir evolução. Em ambientes acelerados, essa clareza evita decisões "
        "reativas e protege o time de dispersão."
    )
    for idx, idea in enumerate(ideas[:5], start=1):
        app = applications[(idx - 1) % len(applications)]
        paragraphs.append(
            f"O conceito {idx}, \"{idea}\", ganha força quando ligado ao trabalho real. Observe "
            "uma atividade recorrente da sua rotina e faça um diagnóstico simples: objetivo, "
            "restrição, risco e métrica de qualidade. Em seguida, compare com a aplicação "
            f"\"{app}\" e adapte para o seu contexto. Essa tradução da teoria para prática "
            "é o ponto que transforma leitura em competência, porque obriga priorização, "
            "comunicação clara e revisão de execução."
        )
    paragraphs.append(
        "Feche a lição registrando um compromisso de baixa complexidade e alto impacto para as "
        "próximas 24 horas. O progresso diário vem da combinação entre foco, repetição e feedback. "
        "Se você mantiver esse ciclo por semanas, os conceitos deixam de ser inspiração pontual "
        "e se tornam padrão de performance."
    )
    return paragraphs


def _ensure_length(items: list[str], minimum: int, prefix: str) -> list[str]:
    result = [item.strip() for item in items if item.strip()]
    while len(result) < minimum:
        result.append(f"{prefix} {len(result) + 1}")
    return result


def _ensure_target_word_count(lesson: Lesson) -> Lesson:
    additions = [
        (
            "Amplie a utilidade desta lição definindo uma métrica de processo e uma métrica de "
            "resultado para os próximos sete dias. A métrica de processo acompanha execução "
            "diária, enquanto a de resultado mostra efeito acumulado. Ao separar os dois níveis, "
            "você evita frustração por esperar impacto imediato e ganha visibilidade sobre a "
            "qualidade da rotina. Se o processo não acontece, o resultado raramente aparece; se "
            "o processo acontece sem qualidade, o resultado aparece tarde e com custo alto."
        ),
        (
            "Também é útil compartilhar a aprendizagem com outra pessoa do time. Ao explicar o "
            "conceito com suas próprias palavras, você revela lacunas de entendimento e transforma "
            "conteúdo passivo em repertório de decisão. Uma conversa curta, orientada por exemplos "
            "reais da semana, costuma acelerar retenção e criar compromisso mútuo. Esse mecanismo "
            "social aumenta a chance de continuidade e reduz o risco de a leitura virar apenas um "
            "insight isolado sem aplicação concreta."
        ),
        (
            "Finalize revisitando a pergunta de reflexão e transformando a resposta em um plano "
            "enxuto: o que começar, o que parar e o que manter. Esse fechamento ajuda a reduzir "
            "ambiguidade e converte intenção em ação observável. Em ciclos curtos, os ganhos vêm "
            "da clareza repetida: menos decisões ad hoc, mais critério, mais consistência e melhor "
            "uso do tempo. O objetivo da leitura diária é justamente esse: melhorar a execução "
            "real sem depender de motivação extraordinária."
        ),
    ]
    updated = lesson
    idx = 0
    while updated.word_count() < 900 and idx < len(additions):
        updated = replace(updated, guided_reading=[*updated.guided_reading, additions[idx]])
        idx += 1
    if updated.word_count() < 900:
        updated = replace(
            updated,
            guided_reading=[
                *updated.guided_reading,
                (
                    "Ajuste final: escolha uma acao objetiva para hoje, acompanhe sua execucao e "
                    "registre o aprendizado em linguagem simples para consolidar a evolucao."
                ),
            ],
        )
    return updated


def _try_refine_with_openai(
    base: Lesson,
    api_key: str,
    model: str,
) -> Lesson | None:
    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("OpenAI SDK indisponível, mantendo texto base. Erro: %s", exc)
        return None

    prompt_payload = {
        "day": base.day,
        "title": base.title,
        "author": base.author,
        "theme": base.theme,
        "central_idea": base.central_idea,
        "concepts": base.concepts,
        "practical_applications": base.practical_applications,
        "reflection_question": base.reflection_question,
        "guided_reading": base.guided_reading,
        "summary_bullets": base.summary_bullets,
        "optional_quote": base.optional_quote,
    }

    instruction = (
        "Você é um editor em português do Brasil. Reescreva a lição para soar mais fluida e "
        "prática, mantendo o mesmo conteúdo e estrutura. Regras: manter exatamente 5 conceitos, "
        "3 aplicações e 3 bullets de resumo; manter 1 pergunta de reflexão; citação opcional com "
        "até 2 linhas; tamanho alvo entre 900 e 1400 palavras e nunca acima de 1600. "
        "Responda somente em JSON com as mesmas chaves de entrada."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=0.5,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or ""
        parsed = json.loads(_extract_json(content))
        lesson = Lesson(
            day=int(parsed["day"]),
            title=str(parsed["title"]),
            author=str(parsed["author"]),
            theme=str(parsed["theme"]),
            central_idea=str(parsed["central_idea"]),
            concepts=[str(item) for item in parsed["concepts"]][:5],
            practical_applications=[str(item) for item in parsed["practical_applications"]][:3],
            reflection_question=str(parsed["reflection_question"]),
            guided_reading=[str(item) for item in parsed["guided_reading"]],
            summary_bullets=[str(item) for item in parsed["summary_bullets"]][:3],
            optional_quote=str(parsed["optional_quote"]).strip()
            if parsed.get("optional_quote")
            else None,
        )
    except Exception as exc:
        logger.warning("Falha ao refinar com OpenAI, mantendo texto base. Erro: %s", exc)
        return None

    if lesson.word_count() < 900:
        logger.warning("Refino da IA ficou curto demais (%s palavras), mantendo base.", lesson.word_count())
        return None
    return lesson


def _extract_json(content: str) -> str:
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return content
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Resposta da IA sem JSON válido.")
    return content[start : end + 1]
