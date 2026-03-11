import time
from typing import Any, Optional

from payos import APIError, PayOS, WebhookError
from payos.types import CreatePaymentLinkRequest

from app.payments.base import DonationRequest, PaymentGateway, PaymentLink


class PayOSGateway(PaymentGateway):
    id = "payos"
    display_name = "PayOS"

    def __init__(self, client_id: str, api_key: str, checksum_key: str, return_url: str, cancel_url: str):
        if not client_id or not api_key or not checksum_key:
            raise ValueError("PayOS credentials are missing; check PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY")
        if not return_url or not cancel_url:
            raise ValueError("PayOS return/cancel URLs are missing; set PAYOS_RETURN_URL and PAYOS_CANCEL_URL")

        self.return_url = return_url
        self.cancel_url = cancel_url
        self.client = PayOS(client_id=client_id, api_key=api_key, checksum_key=checksum_key)

    def create_donation_link(self, donation: DonationRequest) -> PaymentLink:
        order_code = int(time.time())
        description = donation.message.strip() if donation.message else f"Ung ho tu {donation.name}"

        payload = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=donation.amount,
            description=description,
            return_url=self.return_url,
            cancel_url=self.cancel_url,
            buyer_name=donation.name,
            buyer_email=donation.email,
        )

        try:
            response = self.client.payment_requests.create(payment_data=payload)
        except APIError as exc:  # pragma: no cover - pass through errors for caller to handle
            raise RuntimeError(f"PayOS create payment failed: {exc}") from exc

        checkout_url = self._extract(response, "checkout_url", "checkoutUrl")
        if not checkout_url:
            raise RuntimeError("PayOS response missing checkout URL")

        return PaymentLink(
            url=checkout_url,
            order_code=self._extract(response, "order_code", "orderCode", default=order_code),
            qr_code=self._extract(response, "qr_code", "qrCode"),
            expires_at=self._extract(response, "expired_at", "expiredAt", "expiryTime"),
        )

    def verify_webhook(self, payload: bytes):
        try:
            return self.client.webhooks.verify(payload)
        except WebhookError as exc:  # pragma: no cover - validation failure bubbled up
            raise RuntimeError(f"Invalid PayOS webhook: {exc}") from exc

    def get_payment_status(self, order_code: int):
        try:
            return self.client.payment_requests.get(order_code=order_code)
        except APIError as exc:  # pragma: no cover - bubbled up to caller
            raise RuntimeError(f"Unable to fetch PayOS payment status: {exc}") from exc

    @staticmethod
    def _extract(obj: Any, *keys: str, default: Optional[Any] = None) -> Optional[Any]:
        """Helper to read both snake_case and camelCase attributes/dict keys."""
        for key in keys:
            if hasattr(obj, key):
                return getattr(obj, key)
            camel_fallback = key[0].lower() + key[1:] if key and key[0].isupper() else None
            if camel_fallback and hasattr(obj, camel_fallback):
                return getattr(obj, camel_fallback)
            if isinstance(obj, dict) and key in obj:
                return obj[key]
        return default
