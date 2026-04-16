from __future__ import annotations

from app.models import BookEntry

_SYSTEM_MESSAGE = "You are an academic analyst writing in Brazilian Portuguese."

_ACADEMIC_ANALYSIS_PROMPT = """
Escreva uma analise academica aprofundada do livro informado.

Diretrizes:
- objetivo: maximizar profundidade, clareza e completude
- linguagem: profissional, objetiva e didatica
- explique o que, como e por que
- conecte conceitos, evidencias, exemplos e implicacoes
- inclua contrapontos e limitacoes
- nao use parser-friendly formatting forcado
- nao escreva em formato de lista mecanica
- nao mencione que voce e uma IA

Estrutura recomendada (pode adaptar fluentemente):
1) Tese central e problema tratado
2) Arquitetura do argumento ao longo da obra
3) Conceitos estruturantes e relacoes entre eles
4) Evidencias, exemplos e casos relevantes
5) Implicacoes praticas (trabalho, decisao, vida intelectual)
6) Limites, criticas e condicoes de validade
7) Sintese interpretativa final

Entregue o texto final completo em portugues do Brasil.
""".strip()


def generate_academic_analysis_with_openai(
    entry: BookEntry,
    *,
    openai_api_key: str | None,
    openai_model: str,
) -> str:
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY ausente. O v2 requer geracao academica com IA.")
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"SDK OpenAI indisponivel para analise academica: {exc}") from exc

    client = OpenAI(api_key=openai_api_key.strip())
    user_message = _build_user_message(entry)
    response = client.chat.completions.create(
        model=(openai_model or "gpt-4.1").strip(),
        temperature=0.25,
        messages=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": user_message},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("OpenAI retornou analise academica vazia.")
    return content


def _build_user_message(entry: BookEntry) -> str:
    ideas = "\n".join([f"- {item}" for item in entry.key_ideas])
    apps = "\n".join([f"- {item}" for item in entry.practical_applications])
    category = entry.category.strip() if entry.category else "-"
    quote = entry.optional_quote.strip() if entry.optional_quote else "-"
    return (
        f"{_ACADEMIC_ANALYSIS_PROMPT}\n\n"
        "Livro informado:\n"
        f"Titulo: {entry.title}\n"
        f"Autor: {entry.author}\n"
        f"Area: {category}\n"
        f"Tema central: {entry.theme}\n\n"
        "Contexto base:\n"
        f"Ideias iniciais:\n{ideas}\n\n"
        f"Aplicacoes sugeridas:\n{apps}\n\n"
        f"Pergunta de reflexao base: {entry.reflection_question}\n"
        f"Citacao base: {quote}\n"
    )

