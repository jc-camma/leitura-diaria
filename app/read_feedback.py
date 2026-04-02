from __future__ import annotations

import html
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from app.state import PendingReadConfirmation, StateStore


logger = logging.getLogger(__name__)

CONFIRM_READ_PATH = "/confirm-read"


def build_read_confirmation_url(base_url: str, token: str) -> str:
    base = base_url.rstrip("/")
    query = urlencode({"token": token})
    return f"{base}{CONFIRM_READ_PATH}?{query}"


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


def serve_read_feedback(state_file: Path, host: str, port: int) -> None:
    handler = _build_handler(state_file)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info("Servidor de confirmacao de leitura em http://%s:%s%s", host, port, CONFIRM_READ_PATH)
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
                    "Confirmacao de leitura ativa.",
                    "Use o link recebido no email para confirmar a leitura.",
                )
                return

            if parsed.path != CONFIRM_READ_PATH:
                self._send_html(
                    HTTPStatus.NOT_FOUND,
                    "Pagina nao encontrada.",
                    "Verifique o link de confirmacao e tente novamente.",
                )
                return

            token = parse_qs(parsed.query).get("token", [""])[0].strip()
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

