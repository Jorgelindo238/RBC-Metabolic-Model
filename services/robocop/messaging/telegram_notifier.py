from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx


def _read_env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_optional_int(name: str) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _read_timeout(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        timeout = float(raw.strip())
    except ValueError:
        return default
    return timeout if timeout > 0 else default


@dataclass(frozen=True)
class TelegramNotifierConfig:
    enabled: bool
    bot_token: str
    chat_id: str
    api_base_url: str = "https://api.telegram.org"
    parse_mode: str = "HTML"
    timeout_seconds: float = 10.0
    message_thread_id: Optional[int] = None

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.bot_token and self.chat_id)


class TelegramNotifier:
    def __init__(self, config: TelegramNotifierConfig):
        self.config = config

    @property
    def is_enabled(self) -> bool:
        return self.config.is_configured

    def send_text(self, message: str) -> dict[str, Any]:
        if not self.is_enabled:
            return {"ok": False, "sent": False, "reason": "disabled"}

        payload: dict[str, Any] = {
            "chat_id": self.config.chat_id,
            "text": message,
            "parse_mode": self.config.parse_mode,
            "disable_web_page_preview": True,
        }
        if self.config.message_thread_id is not None:
            payload["message_thread_id"] = self.config.message_thread_id

        endpoint = (
            f"{self.config.api_base_url.rstrip('/')}/bot{self.config.bot_token}/sendMessage"
        )
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict) or not data.get("ok"):
            raise RuntimeError(f"Telegram API returned a non-ok response: {data!r}")
        return data


def build_telegram_notifier_from_env(
    prefix: str = "ROBOCOP_TELEGRAM_",
) -> TelegramNotifier:
    config = TelegramNotifierConfig(
        enabled=_read_env_flag(f"{prefix}ENABLED", default=False),
        bot_token=os.getenv(f"{prefix}BOT_TOKEN", "").strip(),
        chat_id=os.getenv(f"{prefix}CHAT_ID", "").strip(),
        api_base_url=os.getenv(f"{prefix}API_BASE_URL", "https://api.telegram.org").strip()
        or "https://api.telegram.org",
        parse_mode=os.getenv(f"{prefix}PARSE_MODE", "HTML").strip() or "HTML",
        timeout_seconds=_read_timeout(f"{prefix}TIMEOUT_SECONDS", default=10.0),
        message_thread_id=_read_optional_int(f"{prefix}MESSAGE_THREAD_ID"),
    )
    return TelegramNotifier(config)
