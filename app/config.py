from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUT_DIR = ROOT_DIR / "out"
BOOKS_FILE = DATA_DIR / "books_365.json"
STATE_FILE = DATA_DIR / "state.json"


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    email_from: str
    email_to: str


@dataclass(frozen=True)
class RuntimePaths:
    data_file: Path = BOOKS_FILE
    state_file: Path = STATE_FILE
    out_dir: Path = OUT_DIR
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    youtube_api_key: str | None = None
    read_confirm_base_url: str | None = None


class ConfigError(RuntimeError):
    """Raised when mandatory configuration is missing."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def load_env_only() -> None:
    load_dotenv()


def runtime_paths() -> RuntimePaths:
    load_dotenv()
    return RuntimePaths(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        read_confirm_base_url=os.getenv("READ_CONFIRM_BASE_URL", "").strip() or None,
    )


def load_smtp_config() -> SmtpConfig:
    load_dotenv()
    smtp = SmtpConfig(
        host=_required_env("SMTP_HOST"),
        port=int(_required_env("SMTP_PORT")),
        user=_required_env("SMTP_USER"),
        password=_required_env("SMTP_PASS"),
        email_from=_required_env("EMAIL_FROM"),
        email_to=_required_env("EMAIL_TO"),
    )
    return smtp
