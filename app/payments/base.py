from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class DonationRequest:
    name: str
    email: str
    message: str
    amount: int


@dataclass
class PaymentLink:
    url: str
    order_code: int
    qr_code: Optional[str] = None
    expires_at: Optional[str] = None


class PaymentGateway(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier of the gateway."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human readable gateway name."""

    @abstractmethod
    def create_donation_link(self, donation: DonationRequest) -> PaymentLink:
        """Create a payment link for a donation request."""

    @abstractmethod
    def verify_webhook(self, payload: bytes):
        """Verify webhook payload and return parsed data if valid."""

    @abstractmethod
    def get_payment_status(self, order_code: int):
        """Fetch payment status for an order code."""


class WebhookHandler(Protocol):
    def __call__(self, data) -> None:
        ...
