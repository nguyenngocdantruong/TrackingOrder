from typing import Dict, Optional

from app.payments.base import PaymentGateway


class PaymentGatewayRegistry:
    def __init__(self):
        self._gateways: Dict[str, PaymentGateway] = {}

    def register(self, gateway: PaymentGateway):
        self._gateways[gateway.id] = gateway

    def get_gateway(self, gateway_id: str) -> Optional[PaymentGateway]:
        return self._gateways.get(gateway_id)

    def list_gateways(self):
        return list(self._gateways.values())


def init_gateways(app):
    """Initialize and register available gateways once the app config is ready."""
    from app.payments.payos_gateway import PayOSGateway

    default_return = app.config.get("PAYOS_RETURN_URL")
    default_cancel = app.config.get("PAYOS_CANCEL_URL")

    try:
        payos_gateway = PayOSGateway(
            client_id=app.config.get("PAYOS_CLIENT_ID"),
            api_key=app.config.get("PAYOS_API_KEY"),
            checksum_key=app.config.get("PAYOS_CHECKSUM_KEY"),
            return_url=default_return,
            cancel_url=default_cancel,
        )
        registry.register(payos_gateway)
    except Exception as exc:  # pragma: no cover - defensive: misconfig will surface in logs
        app.logger.warning("Unable to initialize PayOS gateway: %s", exc)


def get_default_gateway() -> Optional[PaymentGateway]:
    return registry.list_gateways()[0] if registry.list_gateways() else None


registry = PaymentGatewayRegistry()
