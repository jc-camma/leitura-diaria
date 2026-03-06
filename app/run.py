from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from app.config import ConfigError, load_env_only, load_smtp_config, runtime_paths
from app.emailer import EmailSendError, send_lesson_email
from app.lesson import build_lesson, get_entry_for_day, load_books
from app.pdf_gen import generate_lesson_pdf
from app.state import ReadingPlanCompletedError, StateStore


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MBA 15min - envio diário de lições em PDF.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--send-now", action="store_true", help="Gera e envia o PDF por e-mail.")
    group.add_argument("--preview", action="store_true", help="Gera o PDF sem enviar e-mail.")
    parser.add_argument("--force", action="store_true", help="Ignora idempotência do dia.")
    parser.add_argument(
        "--day",
        type=int,
        help="Dia específico (1..365) para gerar/enviar sem alterar state.json.",
    )
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def run() -> int:
    setup_logging()
    args = parse_args()
    paths = runtime_paths()
    load_env_only()

    books = load_books(paths.data_file)
    store = StateStore(paths.state_file)
    current_state = store.load()
    today = date.today()

    manual_day = args.day is not None
    day_to_send = _resolve_day_to_process(args, current_state, today)
    if day_to_send is None:
        logger.info("Licao de hoje ja foi enviada; use --force para reenviar.")
        return 0

    entry = get_entry_for_day(books, day_to_send)
    lesson = build_lesson(
        entry,
        openai_api_key=paths.openai_api_key,
        openai_model=paths.openai_model,
    )
    pdf_path = generate_lesson_pdf(lesson, paths.out_dir, today)
    logger.info("PDF gerado: %s (palavras aproximadas: %s)", pdf_path, lesson.word_count())

    if args.preview:
        logger.info("Modo preview ativo: nenhum e-mail enviado.")
        return 0

    smtp_config = load_smtp_config()
    send_lesson_email(smtp_config, lesson, pdf_path, today)
    logger.info("E-mail enviado para %s", smtp_config.email_to)

    if manual_day:
        logger.info("Envio com --day não altera state.json (modo de teste).")
        return 0

    mode = "force" if args.force and current_state.last_sent_date == today.isoformat() else "auto"
    updated_state = store.register_success(current_state, today, day_to_send, lesson.title, mode)
    store.save(updated_state)
    logger.info(
        "Estado atualizado: last_sent_date=%s, last_day_index=%s",
        updated_state.last_sent_date,
        updated_state.last_day_index,
    )
    return 0


def _resolve_day_to_process(args: argparse.Namespace, state, today: date) -> int | None:
    if args.day is not None:
        if args.day < 1 or args.day > 365:
            raise ValueError("O argumento --day deve estar entre 1 e 365.")
        return args.day

    if args.preview:
        next_day = state.last_day_index + 1
        if next_day > 365:
            raise ReadingPlanCompletedError("Todas as 365 leituras já foram concluídas.")
        return next_day

    if not StateStore.can_send_on(state, today, force=args.force):
        return None
    return StateStore.resolve_day_index_for_send(state, today, force=args.force)


def main() -> None:
    try:
        code = run()
    except (ConfigError, ValueError, ReadingPlanCompletedError, RuntimeError, EmailSendError) as exc:
        logger.error("%s", exc)
        code = 1
    except Exception as exc:  # pragma: no cover
        logger.exception("Falha inesperada: %s", exc)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
