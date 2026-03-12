"""
Notification service for sending notifications through various providers.
"""
from typing import List, Optional
from flask import current_app

from app.notifications.registry import registry
from app.notifications.base import NotificationResult


class NotificationService:
    """Service for sending notifications to users through configured providers."""
    
    @staticmethod
    def send_to_user(user, message: str, parse_mode: Optional[str] = 'Markdown', **kwargs) -> List[NotificationResult]:
        """
        Send notification to a user through all their configured channels.
        
        Args:
            user: User object with settings containing notification preferences
            message: Message text to send
            parse_mode: Parse mode for formatting (Markdown, HTML, etc.)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            List of NotificationResult for each provider used
        """
        if not user or not user.settings:
            return []
        
        # Check if notifications are enabled
        if not user.settings.get('notifyEnabled', True):
            if current_app:
                current_app.logger.info(
                    "Notifications disabled for user %s",
                    user.id
                )
            return []
        
        results = []
        
        # Send via Telegram if configured
        telegram_chat_id = user.settings.get('telegramChatId')
        if telegram_chat_id:
            telegram_provider = registry.get_provider('telegram')
            if telegram_provider and telegram_provider.is_configured():
                result = telegram_provider.send_message(
                    telegram_chat_id,
                    message,
                    parse_mode,
                    **kwargs
                )
                results.append(result)
        
        # Send via Zalo if configured
        zalo_account_id = user.settings.get('zaloAccountId')
        if zalo_account_id:
            zalo_provider = registry.get_provider('zalo')
            if zalo_provider and zalo_provider.is_configured():
                result = zalo_provider.send_message(
                    zalo_account_id,
                    message,
                    parse_mode,
                    **kwargs
                )
                results.append(result)
        
        return results
    
    @staticmethod
    def send_to_chat_id(chat_id: str, message: str, parse_mode: Optional[str] = 'Markdown', **kwargs) -> Optional[NotificationResult]:
        """
        Send notification directly to a Telegram chat ID.
        This is a compatibility method for existing code.
        
        Args:
            chat_id: Telegram chat ID
            message: Message text
            parse_mode: Parse mode for formatting
            **kwargs: Additional parameters like reply_markup
            
        Returns:
            NotificationResult or None if provider not available
        """
        telegram_provider = registry.get_provider('telegram')
        if telegram_provider and telegram_provider.is_configured():
            return telegram_provider.send_message(
                chat_id,
                message,
                parse_mode,
                **kwargs
            )
        return None
    
    @staticmethod
    def broadcast_to_all_telegram_users(message: str, parse_mode: Optional[str] = None) -> List[NotificationResult]:
        """
        Broadcast a message to all users with Telegram configured.
        
        Args:
            message: Message to broadcast
            parse_mode: Parse mode for formatting
            
        Returns:
            List of NotificationResult for each recipient
        """
        from app.repos.users_repo import UsersRepo
        
        telegram_provider = registry.get_provider('telegram')
        if not telegram_provider or not telegram_provider.is_configured():
            return []
        
        chat_ids = UsersRepo.list_telegram_chat_ids()
        results = []
        
        for chat_id in chat_ids:
            result = telegram_provider.send_message(
                chat_id,
                message,
                parse_mode
            )
            results.append(result)
        
        return results
