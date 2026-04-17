from __future__ import annotations

from app.models import BookEntry

_SYSTEM_MESSAGE = "You are an academic analyst and study guide writer in Brazilian Portuguese."

_ACADEMIC_ANALYSIS_PROMPT = """
Escreva um guia de leitura completo, profundo e didático do livro informado.

Objetivo:
- permitir que o leitor compreenda não apenas o conteúdo, mas a lógica interna da obra, suas implicações e seu valor intelectual

Tom e estilo:
- português do Brasil, em linguagem fluida, elegante e acessível
- didático, com rigor conceitual
- analítico sem ser pedante
- claro sem simplificar em excesso
- evite superficialidade, repetições, clichês e generalidades vagas

Estrutura obrigatória:

1) Abertura editorial
- título do livro em português
- linha com autor e foco da leitura
- introdução curta: por que este livro importa hoje

2) Resumo do livro
- tese central
- problema principal enfrentado pela obra
- como o argumento se desenvolve ao longo do livro
- quais são os principais momentos de virada, aprofundamento ou inflexão

3) Principais ideias para aprender de verdade
- apresente os conceitos em sequência lógica
- explique cada ideia com clareza e profundidade
- mostre como as ideias se conectam entre si
- inclua exemplos concretos ou aplicações quando possível
- destaque os mecanismos centrais do argumento: como e por que cada ideia funciona

4) Análise crítica e implicações
- quais são as forças do argumento
- possíveis limitações, tensões ou críticas
- quais ideias são mais contraintuitivas
- quais pontos costumam ser mal interpretados
- quando os conceitos funcionam bem, quando falham e por quê
- comparação implícita entre ideias do próprio livro ou com outras abordagens relevantes
- impacto da obra no pensamento contemporâneo

5) Conclusão
- síntese final dos aprendizados essenciais
- o que o leitor realmente deve levar consigo após a leitura

Instruções adicionais:
- evite apenas explicar; interprete
- não resuma de forma mecânica capítulo por capítulo, a menos que isso seja indispensável para a clareza
- priorize relações entre causas, mecanismos, limites e consequências
- adote uma voz analítica, com momentos de posicionamento intelectual claro, sem perder o tom didático

Entregue o texto final completo em português do Brasil.
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
