from __future__ import annotations

import html
import logging
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from app.config import load_env_only, load_smtp_config, runtime_paths
from app.mailer import deliver_lesson_email
from app.main import prepare_daily_artifacts
from app.state import PendingReadConfirmation, ReadingPlanCompletedError, StateStore

logger = logging.getLogger(__name__)

CONFIRM_READ_PATH = "/confirm-read"
SEND_NEXT_READING_PATH = "/send-next-reading"


def build_read_confirmation_url(base_url: str, token: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}{CONFIRM_READ_PATH}?{urlencode({'token': token})}"


def build_send_next_reading_url(base_url: str, token: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}{SEND_NEXT_READING_PATH}?{urlencode({'token': token})}"


def _normalize_route_prefix(base_url: str | None) -> str:
    if not base_url:
        return ""
    raw_path = (urlsplit(base_url).path or "").strip()
    if not raw_path or raw_path == "/":
        return ""
    return "/" + raw_path.strip("/")


def _route_with_prefix(prefix: str, path: str) -> str:
    if not prefix:
        return path
    return f"{prefix}{path}"


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
        logger.exception("Falha ao enviar proxima leitura por link: %s", exc)
        return "send_failed", state.pending_read_confirmation
    return "sent", new_pending


def _deliver_next_reading(state_file: Path, state, day_to_send: int) -> PendingReadConfirmation:
    load_env_only()
    paths = runtime_paths()
    today = date.today()
    tracking_token = StateStore.get_tracking_token_for_lesson(state, day_to_send)

    read_confirmation_url = None
    next_reading_url = None
    if paths.read_confirm_base_url:
        read_confirmation_url = build_read_confirmation_url(paths.read_confirm_base_url, tracking_token)
        next_reading_url = build_send_next_reading_url(paths.read_confirm_base_url, tracking_token)

    artifacts = prepare_daily_artifacts(
        day=day_to_send,
        runtime=paths,
        generation_date=today,
        catalog_year=today.year,
        rebuild_catalog=False,
        read_confirmation_url=read_confirmation_url,
        next_reading_url=next_reading_url,
    )
    deliver_lesson_email(
        load_smtp_config(),
        artifacts.lesson,
        artifacts.pdf_path,
        today,
        youtube_video_url=artifacts.youtube_reference.url,
        youtube_video_title=artifacts.youtube_reference.title,
        read_confirmation_url=read_confirmation_url,
        next_reading_url=next_reading_url,
    )

    store = StateStore(state_file)
    updated_state = store.load()
    updated_state = store.register_success(
        updated_state,
        today,
        day_to_send,
        artifacts.lesson.title,
        "extra",
        tracking_token=tracking_token,
    )
    store.save(updated_state)
    if updated_state.pending_read_confirmation is None:
        raise RuntimeError("Falha ao registrar leitura pendente.")
    return updated_state.pending_read_confirmation


def serve_read_feedback(state_file: Path, host: str, port: int) -> None:
    load_env_only()
    paths = runtime_paths()
    route_prefix = _normalize_route_prefix(paths.read_confirm_base_url)
    handler = _build_handler(state_file, route_prefix)
    confirm_read_path = _route_with_prefix(route_prefix, CONFIRM_READ_PATH)
    send_next_path = _route_with_prefix(route_prefix, SEND_NEXT_READING_PATH)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info(
        "Servidor de feedback em http://%s:%s%s e http://%s:%s%s",
        host,
        port,
        confirm_read_path,
        host,
        port,
        send_next_path,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Servidor interrompido.")
    finally:
        server.server_close()


def _build_handler(state_file: Path, route_prefix: str = "") -> type[BaseHTTPRequestHandler]:
    home_path = route_prefix or "/"
    confirm_read_path = _route_with_prefix(route_prefix, CONFIRM_READ_PATH)
    send_next_path = _route_with_prefix(route_prefix, SEND_NEXT_READING_PATH)
    valid_paths = {confirm_read_path, send_next_path}

    class ReadFeedbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            if parsed.path in {"/", home_path}:
                self._send_html(
                    HTTPStatus.OK,
                    "Feedback de leitura ativo.",
                    "Use os links recebidos no email para confirmar a leitura ou pedir a proxima.",
                )
                return
            if parsed.path not in valid_paths:
                self._send_html(HTTPStatus.NOT_FOUND, "Pagina nao encontrada.", "Verifique o link e tente novamente.")
                return

            token = parse_qs(parsed.query).get("token", [""])[0].strip()
            if parsed.path == send_next_path:
                status, pending = send_next_reading_from_token(state_file, token)
                if status == "sent":
                    self._send_html(HTTPStatus.OK, "Proxima leitura enviada.", f"Nova leitura enviada: {_label(pending)}.")
                    return
                if status == "completed":
                    self._send_html(HTTPStatus.OK, "Plano concluido.", "Todas as 365 leituras ja foram enviadas.")
                    return
                if status == "send_failed":
                    self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Falha no envio.", "Verifique logs e configuracao.")
                    return
                self._send_html(HTTPStatus.BAD_REQUEST, "Link invalido ou expirado.", "Reenvie com --force ou confirme via CLI.")
                return

            status, pending = confirm_read_from_token(state_file, token)
            if status == "confirmed":
                self._send_html(HTTPStatus.OK, "Leitura confirmada.", f"Recebemos a confirmacao da {_label(pending)}.")
                return
            if status == "already_confirmed":
                self._send_html(HTTPStatus.OK, "Leitura ja confirmada.", f"Nada a fazer para {_label(pending)}.")
                return
            self._send_html(HTTPStatus.BAD_REQUEST, "Link invalido ou expirado.", "Reenvie com --force ou confirme via CLI.")

        def log_message(self, format: str, *args: object) -> None:
            logger.info("%s - %s", self.address_string(), format % args)

        def _send_html(self, status: HTTPStatus, title: str, message: str) -> None:
            title_text = html.escape(title)
            message_text = html.escape(message)
            body = (
                "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                f"<title>{title_text}</title>"
                "<style>body{font-family:Segoe UI,Arial,sans-serif;background:#f5f7fb;color:#1f2937;"
                "margin:0;padding:32px}.card{max-width:640px;margin:48px auto;background:#fff;border-radius:16px;"
                "padding:32px;box-shadow:0 20px 45px rgba(15,23,42,.08)}h1{margin-top:0;font-size:28px}"
                "p{line-height:1.6;font-size:16px}</style></head><body><div class='card'>"
                f"<h1>{title_text}</h1><p>{message_text}</p></div></body></html>"
            ).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ReadFeedbackHandler


def _label(pending: PendingReadConfirmation | None) -> str:
    if pending is None:
        return "leitura"
    if pending.title:
        return f"leitura do Dia {pending.day}: {pending.title}"
    return f"leitura do Dia {pending.day}"
