from app.providers.spx_vn_provider import SPXVNProvider
from app.providers.lex_provider import LEXProvider

class ProviderRegistry:
    def __init__(self):
        self._providers = {
            'shopee_express_vn': SPXVNProvider(),
            'lex': LEXProvider()
        }

    def get_provider(self, provider_id):
        return self._providers.get(provider_id)

    def find_provider_for(self, tracking_number):
        for provider in self._providers.values():
            if provider.supports(tracking_number):
                return provider
        return None

    def list_providers(self):
        return [(p.id, p.displayName) for p in self._providers.values()]

registry = ProviderRegistry()
