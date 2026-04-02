from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from app.config import ConfigError, load_env_only, load_smtp_config, runtime_paths
from app.main import build_refined_lesson
from app.mailer import EmailSendError, deliver_lesson_email
from app.pdf_exporter import export_pdf
from app.read_feedback import (
    build_read_confirmation_url,
    confirm_latest_pending_read,
    confirm_read_from_token,
    serve_read_feedback,
)
from app.reading_plan import select_daily_entry
from app.state import ReadingPlanCompletedError, State, StateStore
from app.youtube import find_most_relevant_video


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MBA 15min - envio diario de licoes em PDF.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--send-now", action="store_true", help="Gera e envia o PDF por e-mail.")
    group.add_argument("--preview", action="store_true", help="Gera o PDF sem enviar e-mail.")
    group.add_argument(
        "--serve-feedback",
        action="store_true",
        help="Inicia um servidor HTTP simples para confirmar leituras por link.",
    )
    group.add_argument(
        "--mark-last-read",
        action="store_true",
        help="Marca a leitura pendente atual como lida.",
    )
    group.add_argument(
        "--mark-read-token",
        metavar="TOKEN",
        help="Confirma a leitura usando o token do link de feedback.",
    )
    parser.add_argument("--force", action="store_true", help="Ignora a idempotencia do dia.")
    parser.add_argument(
        "--day",
        type=int,
        help="Dia especifico (1..365) para gerar/enviar sem alterar state.json.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor de feedback.")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor de feedback.")
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

    if args.serve_feedback:
        serve_read_feedback(paths.state_file, args.host, args.port)
        return 0

    store = StateStore(paths.state_file)
    current_state = store.load()
    today = date.today()

    if args.mark_last_read:
        return _mark_latest_pending_read(paths.state_file)

    if args.mark_read_token:
        return _mark_read_by_token(paths.state_file, args.mark_read_token)

    manual_day = args.day is not None
    day_to_send = _resolve_day_to_process(args, current_state, today)
    if day_to_send is None:
        logger.info(StateStore.block_reason(current_state, today, force=args.force) or "Envio bloqueado.")
        return 0

    entry = select_daily_entry(paths.data_file, day_to_send)
    lesson = build_refined_lesson(entry, openai_api_key=paths.openai_api_key, openai_model=paths.openai_model)
    youtube_ref = find_most_relevant_video(lesson, youtube_api_key=paths.youtube_api_key)
    tracking_token = None if manual_day or args.preview else StateStore.get_tracking_token_for_lesson(current_state, day_to_send)
    read_confirmation_url = None
    if tracking_token and paths.read_confirm_base_url:
        read_confirmation_url = build_read_confirmation_url(paths.read_confirm_base_url, tracking_token)
    pdf_path = export_pdf(
        lesson,
        paths.out_dir,
        today,
        youtube_video_url=youtube_ref.url,
        youtube_video_title=youtube_ref.title,
        read_confirmation_url=read_confirmation_url,
    )
    logger.info("PDF gerado: %s (palavras aproximadas: %s)", pdf_path, lesson.word_count())
    logger.info("Link YouTube (%s): %s", youtube_ref.source, youtube_ref.url)

    if args.preview:
        logger.info("Modo preview ativo: nenhum e-mail enviado.")
        return 0

    smtp_config = load_smtp_config()

    deliver_lesson_email(
        smtp_config,
        lesson,
        pdf_path,
        today,
        youtube_video_url=youtube_ref.url,
        youtube_video_title=youtube_ref.title,
        read_confirmation_url=read_confirmation_url,
    )
    logger.info("E-mail enviado para %s", smtp_config.email_to)

    if not manual_day and not read_confirmation_url:
        logger.info(
            "Link de confirmacao nao incluido no e-mail nem no PDF. Configure READ_CONFIRM_BASE_URL ou use --mark-last-read."
        )

    if manual_day:
        logger.info("Envio com --day nao altera state.json (modo de teste).")
        return 0

    mode = "force" if args.force else "auto"
    updated_state = store.register_success(
        current_state,
        today,
        day_to_send,
        lesson.title,
        mode,
        tracking_token=tracking_token,
    )
    store.save(updated_state)
    logger.info(
        "Estado atualizado: last_sent_date=%s, last_day_index=%s, leitura_pendente_dia=%s",
        updated_state.last_sent_date,
        updated_state.last_day_index,
        updated_state.pending_read_confirmation.day if updated_state.pending_read_confirmation else None,
    )
    return 0


def _resolve_day_to_process(args: argparse.Namespace, state: State, today: date) -> int | None:
    if args.day is not None:
        if args.day < 1 or args.day > 365:
            raise ValueError("O argumento --day deve estar entre 1 e 365.")
        return args.day

    if args.preview:
        next_day = state.last_day_index + 1
        if next_day > 365:
            raise ReadingPlanCompletedError("Todas as 365 leituras ja foram concluidas.")
        return next_day

    if not StateStore.can_send_on(state, today, force=args.force):
        return None
    return StateStore.resolve_day_index_for_send(state, today, force=args.force)


def _mark_latest_pending_read(state_file: Path) -> int:
    status, pending = confirm_latest_pending_read(state_file)
    if status == "confirmed" and pending is not None:
        logger.info("Leitura do Dia %s marcada como lida.", pending.day)
        return 0
    if status == "already_confirmed" and pending is not None:
        logger.info("A leitura do Dia %s ja estava confirmada.", pending.day)
        return 0
    logger.info("Nao ha leitura pendente para confirmar.")
    return 0


def _mark_read_by_token(state_file: Path, token: str) -> int:
    status, pending = confirm_read_from_token(state_file, token)
    if status == "confirmed" and pending is not None:
        logger.info("Leitura do Dia %s confirmada pelo token.", pending.day)
        return 0
    if status == "already_confirmed" and pending is not None:
        logger.info("A leitura do Dia %s ja estava confirmada.", pending.day)
        return 0
    logger.error("Token de confirmacao invalido ou expirado.")
    return 1


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
