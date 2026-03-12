"""
Backward compatibility wrapper for TelegramNotifier.
This class is deprecated - use NotificationService instead.
"""
from app.notifications.service import NotificationService


class TelegramNotifier:
    """
    Deprecated: Use NotificationService instead.
    This class is maintained for backward compatibility.
    """
    
    @staticmethod
    def send_message(chat_id, text, parse_mode='Markdown', reply_markup=None):
        """
        Send a Telegram message (backward compatibility method).
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)
            reply_markup: Optional reply markup
            
        Returns:
            Boolean indicating success (for backward compatibility)
        """
        kwargs = {}
        if reply_markup:
            kwargs['reply_markup'] = reply_markup
        
        result = NotificationService.send_to_chat_id(
            chat_id,
            text,
            parse_mode,
            **kwargs
        )
        
        return result.success if result else False

