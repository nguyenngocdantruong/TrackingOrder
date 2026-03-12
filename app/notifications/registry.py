from typing import Dict, List, Optional

from app.notifications.base import NotificationProvider


class NotificationProviderRegistry:
    """Registry for managing notification providers."""
    
    def __init__(self):
        self._providers: Dict[str, NotificationProvider] = {}

    def register(self, provider: NotificationProvider):
        """Register a notification provider."""
        self._providers[provider.id] = provider

    def get_provider(self, provider_id: str) -> Optional[NotificationProvider]:
        """Get a provider by its ID."""
        return self._providers.get(provider_id)

    def list_providers(self) -> List[NotificationProvider]:
        """Get all registered providers."""
        return list(self._providers.values())

    def get_configured_providers(self) -> List[NotificationProvider]:
        """Get all properly configured providers."""
        return [p for p in self._providers.values() if p.is_configured()]


def init_notification_providers(app):
    """Initialize and register available notification providers."""
    from app.notifications.telegram_provider import TelegramProvider
    from app.notifications.zalo_bot_provider import ZaloBotProvider

    # Register Telegram provider
    try:
        telegram_token = app.config.get('TELEGRAM_BOT_TOKEN')
        if telegram_token:
            telegram = TelegramProvider(token=telegram_token)
            registry.register(telegram)
            app.logger.info("Registered Telegram notification provider")
    except Exception as exc:
        app.logger.warning("Unable to initialize Telegram provider: %s", exc)

    # Register Zalo bot provider
    try:
        zalo_bot_token = app.config.get('ZALO_BOT_TOKEN')
        if zalo_bot_token:
            zalo_bot = ZaloBotProvider(token=zalo_bot_token)
            registry.register(zalo_bot)
            app.logger.info("Registered Zalo Bot notification provider")
    except Exception as exc:
        app.logger.warning("Unable to initialize Zalo bot provider: %s", exc)


# Global registry instance
registry = NotificationProviderRegistry()
