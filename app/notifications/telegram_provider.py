import requests
from typing import Optional
from flask import current_app

from app.notifications.base import NotificationProvider, NotificationResult


class TelegramProvider(NotificationProvider):
    """Telegram notification provider implementation."""
    
    def __init__(self, token: str):
        """
        Initialize Telegram provider.
        
        Args:
            token: Telegram Bot API token
        """
        self._token = token

    @property
    def id(self) -> str:
        return "telegram"

    @property
    def display_name(self) -> str:
        return "Telegram"

    def send_message(
        self,
        recipient_id: str,
        text: str,
        parse_mode: Optional[str] = 'Markdown',
        **kwargs
    ) -> NotificationResult:
        """
        Send a message via Telegram.
        
        Args:
            recipient_id: Telegram chat_id
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)
            **kwargs: Additional parameters like reply_markup
            
        Returns:
            NotificationResult with success status
        """
        if not self._token:
            return NotificationResult(
                success=False,
                error_message="Telegram token not configured"
            )

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            'chat_id': recipient_id,
            'text': text
        }

        if parse_mode:
            payload['parse_mode'] = parse_mode

        # Handle additional kwargs like reply_markup
        reply_markup = kwargs.get('reply_markup')
        if reply_markup:
            payload['reply_markup'] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=10)
            
            if current_app:
                current_app.logger.info(
                    "[Telegram] Message sent to %s: %s",
                    recipient_id,
                    text[:50] + "..." if len(text) > 50 else text
                )
            
            if response.status_code == 200:
                return NotificationResult(
                    success=True,
                    response_data=response.json()
                )
            else:
                return NotificationResult(
                    success=False,
                    error_message=f"Telegram API error: {response.status_code}",
                    response_data=response.json() if response.text else None
                )
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Telegram error: {e}")
            return NotificationResult(
                success=False,
                error_message=str(e)
            )

    def is_configured(self) -> bool:
        """Check if Telegram provider is configured."""
        return self._token is not None and self._token != ""

    def supports_recipient(self, recipient_id: Optional[str]) -> bool:
        """Check if recipient_id is valid for Telegram."""
        if not recipient_id:
            return False
        # Telegram chat_id should be numeric or start with @
        return recipient_id.lstrip('-').isdigit() or recipient_id.startswith('@')
