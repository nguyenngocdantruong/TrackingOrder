from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class NotificationMessage:
    """Represents a notification message to be sent."""
    recipient_id: str
    text: str
    parse_mode: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class NotificationResult:
    """Result of a notification send operation."""
    success: bool
    error_message: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


class NotificationProvider(ABC):
    """Base class for all notification providers (Telegram, Zalo, etc.)."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier of the notification provider (e.g., 'telegram', 'zalo')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name of the notification provider."""
        pass

    @abstractmethod
    def send_message(
        self,
        recipient_id: str,
        text: str,
        parse_mode: Optional[str] = None,
        **kwargs
    ) -> NotificationResult:
        """
        Send a notification message to a recipient.
        
        Args:
            recipient_id: The recipient identifier (e.g., chat_id for Telegram, user_id for Zalo)
            text: The message text
            parse_mode: Optional formatting mode (e.g., 'Markdown', 'HTML')
            **kwargs: Additional provider-specific parameters
            
        Returns:
            NotificationResult with success status and optional error message
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if this provider is properly configured and ready to send notifications.
        
        Returns:
            True if the provider is configured, False otherwise
        """
        pass

    def supports_recipient(self, recipient_id: Optional[str]) -> bool:
        """
        Check if this provider can send to the given recipient.
        
        Args:
            recipient_id: The recipient identifier to check
            
        Returns:
            True if the provider can send to this recipient, False otherwise
        """
        return recipient_id is not None and recipient_id != ""
