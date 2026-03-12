from typing import Optional
import requests
from flask import current_app

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

        url = f"https://bot-api.zaloplatforms.com/bot{self._token}/sendMessage"
        payload = {
            'chat_id': str(recipient_id),
            'text': text,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json() if response.text else {}

            if current_app:
                preview = text[:50] + "..." if len(text) > 50 else text
                current_app.logger.info("[Zalo] Message sent to %s: %s", recipient_id, preview)

            if response.status_code == 200 and data.get('ok', False):
                return NotificationResult(success=True, response_data=data.get('result'))

            return NotificationResult(
                success=False,
                error_message=data.get('description') or f"Zalo API error: {response.status_code}",
                response_data=data or None,
            )
        except Exception as exc:  # pragma: no cover - network errors
            if current_app:
                current_app.logger.error("Zalo bot error: %s", exc)
            return NotificationResult(success=False, error_message=str(exc))

    def is_configured(self) -> bool:
        return bool(self._token)

    def supports_recipient(self, recipient_id: Optional[str]) -> bool:
        return bool(recipient_id)
