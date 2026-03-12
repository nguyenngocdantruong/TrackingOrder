import asyncio
from typing import Optional
from flask import current_app
import zalo_bot

from app.notifications.base import NotificationProvider, NotificationResult


class ZaloBotProvider(NotificationProvider):
    """Zalo Bot notification provider implemented via python-zalo-bot."""

    def __init__(self, token: str):
        self._token = token

    @property
    def id(self) -> str:
        return "zalo"

    @property
    def display_name(self) -> str:
        return "Zalo Bot"

    def send_message(
        self,
        recipient_id: str,
        text: str,
        parse_mode: Optional[str] = None,
        **kwargs,
    ) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(success=False, error_message="Zalo bot not configured")

        async def _send():
            bot = zalo_bot.Bot(self._token)
            async with bot:
                return await bot.send_message(str(recipient_id), text)

        try:
            message = asyncio.run(_send())
            response_data = None
            if message:
                response_data = {
                    "message_id": getattr(message, "id", None),
                    "chat_id": getattr(message.chat, "id", None) if getattr(message, "chat", None) else None,
                }
            if current_app:
                current_app.logger.info("[Zalo] Message sent to %s", recipient_id)
            return NotificationResult(success=True, response_data=response_data)
        except Exception as exc:  # pragma: no cover - network errors
            if current_app:
                current_app.logger.error("Zalo bot error: %s", exc)
            return NotificationResult(success=False, error_message=str(exc))

    def is_configured(self) -> bool:
        return bool(self._token)

    def supports_recipient(self, recipient_id: Optional[str]) -> bool:
        return bool(recipient_id)
