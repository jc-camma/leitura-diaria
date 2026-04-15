from __future__ import annotations

import html
import logging
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from app.state import PendingReadConfirmation, ReadingPlanCompletedError, StateStore


logger = logging.getLogger(__name__)

CONFIRM_READ_PATH = "/confirm-read"
SEND_NEXT_READING_PATH = "/send-next-reading"


def build_read_confirmation_url(base_url: str, token: str) -> str:
    base = base_url.rstrip("/")
    query = urlencode({"token": token})
    return f"{base}{CONFIRM_READ_PATH}?{query}"


def build_send_next_reading_url(base_url: str, token: str) -> str:
    base = base_url.rstrip("/")
    query = urlencode({"token": token})
    return f"{base}{SEND_NEXT_READING_PATH}?{query}"


def confirm_read_from_token(state_file: Path, token: str) -> tuple[str, PendingReadConfirmation | None]:
    store = StateStore(state_file)
    state = store.load()
    status = StateStore.confirm_pending_read(state, token)
    if status == "confirmed":
        store.save(state)
    return status, state.pending_read_confirmation


def confirm_latest_pending_read(state_file: Path) -> tuple[str, PendingReadConfirmation | None]:
    store = StateStore(state_file)
    state = store.load()
    status = StateStore.confirm_latest_pending_read(state)
    if status == "confirmed":
        store.save(state)
    return status, state.pending_read_confirmation


def send_next_reading_from_token(state_file: Path, token: str) -> tuple[str, PendingReadConfirmation | None]:
    store = StateStore(state_file)
    state = store.load()
    pending = state.pending_read_confirmation
    if pending is None or pending.token != token:
        return "invalid", None

    confirmation_status = StateStore.confirm_pending_read(state, token)
    if confirmation_status == "invalid":
        return "invalid", None

    store.save(state)

    if not StateStore.can_send_additional_on(state):
        return "blocked", state.pending_read_confirmation

    try:
        day_to_send = StateStore.resolve_day_index_for_additional_send(state)
    except ReadingPlanCompletedError:
        return "completed", state.pending_read_confirmation

    try:
        new_pending = _deliver_next_reading(state_file, state, day_to_send)
    except Exception as exc:  # pragma: no cover
        logger.exception("Falha ao enviar proxima leitura a partir do link: %s", exc)
        return "send_failed", state.pending_read_confirmation
    return "sent", new_pending


def _deliver_next_reading(state_file: Path, state, day_to_send: int) -> PendingReadConfirmation:
    from app.config import load_env_only, load_smtp_config, runtime_paths
    from app.main import build_refined_lesson
    from app.mailer import deliver_lesson_email
    from app.pdf_exporter import export_pdf
    from app.reading_plan import select_daily_entry
    from app.youtube import find_most_relevant_video

    load_env_only()
    paths = runtime_paths()
    today = date.today()
    entry = select_daily_entry(paths.data_file, day_to_send)
    lesson = build_refined_lesson(entry, openai_api_key=paths.openai_api_key, openai_model=paths.openai_model)
    youtube_ref = find_most_relevant_video(lesson, youtube_api_key=paths.youtube_api_key)
    tracking_token = StateStore.get_tracking_token_for_lesson(state, day_to_send)

    read_confirmation_url = None
    next_reading_url = None
    if paths.read_confirm_base_url:
        read_confirmation_url = build_read_confirmation_url(paths.read_confirm_base_url, tracking_token)
        next_reading_url = build_send_next_reading_url(paths.read_confirm_base_url, tracking_token)

    pdf_path = export_pdf(
        lesson,
        paths.out_dir,
        today,
        youtube_video_url=youtube_ref.url,
        youtube_video_title=youtube_ref.title,
        read_confirmation_url=read_confirmation_url,
        next_reading_url=next_reading_url,
    )
    deliver_lesson_email(
        load_smtp_config(),
        lesson,
        pdf_path,
        today,
        youtube_video_url=youtube_ref.url,
        youtube_video_title=youtube_ref.title,
        read_confirmation_url=read_confirmation_url,
        next_reading_url=next_reading_url,
    )

    updated_state = StateStore(Path(state_file)).load()
    updated_state = StateStore(state_file).register_success(
        updated_state,
        today,
        day_to_send,
        lesson.title,
        "extra",
        tracking_token=tracking_token,
    )
    StateStore(state_file).save(updated_state)
    if updated_state.pending_read_confirmation is None:
        raise RuntimeError("Falha ao registrar a nova leitura pendente.")
    return updated_state.pending_read_confirmation


def serve_read_feedback(state_file: Path, host: str, port: int) -> None:
    handler = _build_handler(state_file)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info(
        "Servidor de feedback em http://%s:%s%s e http://%s:%s%s",
        host,
        port,
        CONFIRM_READ_PATH,
        host,
        port,
        SEND_NEXT_READING_PATH,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Servidor de confirmacao interrompido.")
    finally:
        server.server_close()


def _build_handler(state_file: Path) -> type[BaseHTTPRequestHandler]:
    class ReadFeedbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            if parsed.path == "/":
                self._send_html(
                    HTTPStatus.OK,
                    "Feedback de leitura ativo.",
                    "Use os links recebidos no email para confirmar a leitura ou pedir a proxima.",
                )
                return

            if parsed.path not in {CONFIRM_READ_PATH, SEND_NEXT_READING_PATH}:
                self._send_html(
                    HTTPStatus.NOT_FOUND,
                    "Pagina nao encontrada.",
                    "Verifique o link de confirmacao e tente novamente.",
                )
                return

            token = parse_qs(parsed.query).get("token", [""])[0].strip()
            if parsed.path == SEND_NEXT_READING_PATH:
                status, pending = send_next_reading_from_token(state_file, token)
                if status == "sent":
                    lesson_text = _format_lesson_label(pending)
                    self._send_html(
                        HTTPStatus.OK,
                        "Proxima leitura enviada com sucesso.",
                        f"A nova leitura foi enviada: {lesson_text}.",
                    )
                    return

                if status == "completed":
                    self._send_html(
                        HTTPStatus.OK,
                        "Plano concluido.",
                        "Todas as 365 leituras ja foram enviadas.",
                    )
                    return

                if status == "send_failed":
                    self._send_html(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "Nao foi possivel enviar a proxima leitura.",
                        "Verifique configuracao SMTP, credenciais e logs do servidor antes de tentar novamente.",
                    )
                    return

                self._send_html(
                    HTTPStatus.BAD_REQUEST,
                    "Link invalido ou expirado.",
                    "Se precisar, reenvie a leitura pendente com --force ou marque manualmente via CLI.",
                )
                return

            status, pending = confirm_read_from_token(state_file, token)

            if status == "confirmed":
                lesson_text = _format_lesson_label(pending)
                self._send_html(
                    HTTPStatus.OK,
                    "Leitura confirmada com sucesso.",
                    f"Recebemos a confirmacao da {lesson_text}.",
                )
                return

            if status == "already_confirmed":
                lesson_text = _format_lesson_label(pending)
                self._send_html(
                    HTTPStatus.OK,
                    "Essa leitura ja estava confirmada.",
                    f"Nada mais precisa ser feito para a {lesson_text}.",
                )
                return

            self._send_html(
                HTTPStatus.BAD_REQUEST,
                "Link invalido ou expirado.",
                "Se precisar, reenvie a leitura pendente com --force ou marque manualmente via CLI.",
            )

        def log_message(self, format: str, *args: object) -> None:
            logger.info("%s - %s", self.address_string(), format % args)

        def _send_html(self, status: HTTPStatus, title: str, message: str) -> None:
            title_text = html.escape(title)
            message_text = html.escape(message)
            body = (
                "<!doctype html>"
                "<html lang='pt-BR'>"
                "<head>"
                "<meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                f"<title>{title_text}</title>"
                "<style>"
                "body{font-family:Segoe UI,Arial,sans-serif;background:#f5f7fb;color:#1f2937;"
                "margin:0;padding:32px;}"
                ".card{max-width:640px;margin:48px auto;background:#fff;border-radius:16px;"
                "padding:32px;box-shadow:0 20px 45px rgba(15,23,42,.08);}"
                "h1{margin-top:0;font-size:28px;}p{line-height:1.6;font-size:16px;}"
                "</style>"
                "</head>"
                "<body><div class='card'>"
                f"<h1>{title_text}</h1>"
                f"<p>{message_text}</p>"
                "</div></body></html>"
            ).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ReadFeedbackHandler


def _format_lesson_label(pending: PendingReadConfirmation | None) -> str:
    if pending is None:
        return "leitura"
    if pending.title:
        return f"leitura do Dia {pending.day}: {pending.title}"
    return f"leitura do Dia {pending.day}"
