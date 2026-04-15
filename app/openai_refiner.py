from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.lesson import BookEntry


_SYSTEM_MESSAGE = (
    "You are a professional analyst and editor writing in Brazilian Portuguese."
)

_BOOK_SUMMARY_PROMPT = (
    "Voce e um analista especializado em livros de nao ficcao, ficcao literaria e obras classicas de pensamento, "
    "com foco em extrair sentido, contexto e implicacoes praticas sem simplificar demais.\n\n"
    "Sua tarefa e gerar um resumo claro, estruturado e pratico do livro informado.\n\n"
    "O texto deve ter aproximadamente 900 a 1200 palavras, o suficiente para cerca de 15 minutos de leitura.\n\n"
    "Use linguagem simples, objetiva e profissional.\n\n"
    "Estruture o conteudo exatamente nas seguintes secoes:\n\n"
    "TITULO DO LIVRO\n"
    "Autor\n"
    "Tema principal\n\n"
    "1. Ideia central\n"
    "   Explique em 2 a 3 paragrafos qual e a tese principal do autor e qual problema o livro busca resolver.\n\n"
    "2. Por que este livro importa\n"
    "   Explique o contexto da obra, por que ela se tornou relevante e quais situacoes praticas ela ajuda a compreender.\n\n"
    "3. Conceitos fundamentais do livro\n"
    "   Liste e explique os conceitos importantes apresentados pelo autor, sem limitar a quantidade.\n\n"
    "   Se o livro for de ficcao, trate como conceitos os temas, conflitos, simbolos, dilemas, mecanismos "
    "narrativos ou perguntas morais que organizam a obra.\n\n"
    "Para cada conceito:\n\n"
    "* nome do conceito\n"
    "* explicacao clara\n"
    "* exemplo pratico de aplicacao no trabalho ou na vida pessoal\n\n"
    "4. Modelo mental ou estrutura apresentada pelo autor\n"
    "   Explique qualquer framework, metodo ou estrutura importante apresentada no livro.\n\n"
    "   Se nao houver framework explicito, descreva a arquitetura narrativa, lente interpretativa ou estrutura "
    "moral que ajuda a compreender a obra.\n\n"
    "5. Exemplo ou historia marcante do livro\n"
    "   Descreva uma historia, estudo de caso, cena ou exemplo que o autor utiliza para ilustrar suas ideias.\n\n"
    "6. Aplicacao pratica\n"
    "   Liste 3 a 5 acoes praticas que uma pessoa poderia comecar a aplicar ja na proxima semana com base nas ideias do livro.\n\n"
    "   Em ficcao, essas acoes podem ser perguntas de leitura, criterios de observacao do mundo, exercicios de "
    "interpretacao ou pequenas mudancas de conduta inspiradas pela obra.\n\n"
    "7. Limitacoes ou criticas possiveis\n"
    "   Explique brevemente possiveis limitacoes das ideias do autor ou contextos em que elas podem nao funcionar.\n\n"
    "8. Sintese final\n"
    "   Conclua com um paragrafo resumindo a principal licao do livro.\n\n"
    "Importante:\n\n"
    "* escreva de forma fluida, sem parecer uma lista mecanica\n"
    "* evite frases genericas\n"
    "* priorize clareza e utilidade pratica\n"
    "* nao invente informacoes que nao existam no livro\n"
    "* nao mencione que voce e uma IA\n\n"
    "Para facilitar a leitura e o parsing do item 3, use blocos no formato:\n"
    "Conceito: <nome>\n"
    "Explicacao: <texto>\n"
    "Exemplo: <texto>\n"
)


def refine_text_with_openai(text: str) -> str:
    load_dotenv()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
    if not api_key:
        logger.info("OPENAI_API_KEY ausente; pulando refino editorial da OpenAI.")
        return text

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("SDK OpenAI indisponivel; mantendo texto local. Erro: %s", exc)
        return text

    client = OpenAI(api_key=api_key)
    user_message = _USER_PROMPT_TEMPLATE.format(generated_text=text)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.4,
                max_tokens=4000,
                messages=[
                    {"role": "system", "content": _SYSTEM_MESSAGE},
                    {"role": "user", "content": user_message},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                logger.warning("OpenAI retornou texto vazio; mantendo versao local.")
                return text
            return content
        except Exception as exc:
            if attempt >= max_retries:
                logger.warning("Falha no refino OpenAI apos %s tentativas: %s", attempt + 1, exc)
                return text
            delay_seconds = 2**attempt
            logger.warning(
                "Erro no refino OpenAI (tentativa %s/%s): %s. Novo retry em %ss.",
                attempt + 1,
                max_retries + 1,
                exc,
                delay_seconds,
            )
            time.sleep(delay_seconds)
    return text


_USER_PROMPT_TEMPLATE = (
    "Rewrite the following text to improve editorial quality.\n\n"
    "Requirements:\n\n"
    "- keep a didactic and concrete tone\n"
    "- explain concepts with plain language, mechanism, and practical example\n"
    "- avoid abstract meta-commentary about the structure of the book\n"
    "- remove repetitive sentence structures\n"
    "- improve transitions without sounding formulaic\n"
    "- reduce generic filler language\n"
    "- preserve meaning\n"
    "- keep the structure and sections intact\n"
    "- keep section titles, numbering, bullet lists, and formatting markers\n"
    "- keep Brazilian Portuguese\n"
    "- make the text sound natural and human-written\n\n"
    "Do not remove sections.\n"
    "Do not add new sections.\n"
    "Do not shorten important content excessively.\n\n"
    "TEXT TO REFINE:\n"
    "{generated_text}"
)


def generate_book_summary_with_openai(
    entry: "BookEntry",
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
) -> str | None:
    load_dotenv()
    api_key = (openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    model = (openai_model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
    if not api_key:
        logger.info("OPENAI_API_KEY ausente; nao foi possivel gerar resumo completo com IA.")
        return None

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("SDK OpenAI indisponivel; mantendo geracao local. Erro: %s", exc)
        return None

    client = OpenAI(api_key=api_key)
    user_message = _build_summary_user_message(entry)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.3,
                max_tokens=5000,
                messages=[
                    {"role": "system", "content": _SYSTEM_MESSAGE},
                    {"role": "user", "content": user_message},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                logger.warning("OpenAI retornou resumo vazio; mantendo geracao local.")
                return None
            return content
        except Exception as exc:
            if attempt >= max_retries:
                logger.warning("Falha na geracao IA apos %s tentativas: %s", attempt + 1, exc)
                return None
            delay_seconds = 2**attempt
            logger.warning(
                "Erro na geracao IA (tentativa %s/%s): %s. Novo retry em %ss.",
                attempt + 1,
                max_retries + 1,
                exc,
                delay_seconds,
            )
            time.sleep(delay_seconds)
    return None


def _build_summary_user_message(entry: "BookEntry") -> str:
    ideas = "\n".join([f"- {item}" for item in entry.key_ideas])
    apps = "\n".join([f"- {item}" for item in entry.practical_applications])
    quote = entry.optional_quote.strip() if entry.optional_quote else "-"
    category = entry.category.strip() if entry.category else "-"
    return (
        f"{_BOOK_SUMMARY_PROMPT}\n\n"
        "Livro informado:\n"
        f"Titulo: {entry.title}\n"
        f"Autor: {entry.author}\n"
        f"Categoria: {category}\n"
        f"Tema principal: {entry.theme}\n\n"
        "Dados de apoio para manter aderencia ao conteudo do livro:\n"
        f"Ideias-chave:\n{ideas}\n\n"
        f"Aplicacoes sugeridas:\n{apps}\n\n"
        f"Pergunta de reflexao base: {entry.reflection_question}\n"
        f"Citacao de apoio: {quote}\n"
    )
