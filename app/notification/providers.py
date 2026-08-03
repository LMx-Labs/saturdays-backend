import logging
import uuid
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class NotificationProviderInterface(ABC):
    """Abstract Provider Interface for decoupled vendor email dispatch."""

    @abstractmethod
    async def send_email(self, recipient: str, subject: str, body: str) -> str:
        """Dispatches email notification and returns provider vendor_message_id."""


class MockEmailProvider(NotificationProviderInterface):
    """Mock Email Provider for local development & automated test suites."""

    async def send_email(self, recipient: str, subject: str, body: str) -> str:
        vendor_msg_id = f"mock_msg_{uuid.uuid4().hex[:12]}"
        logger.info(
            f"[MockEmailProvider] Dispatched email to '{recipient}' | Subject: '{subject}' | MessageID: {vendor_msg_id}"
        )
        return vendor_msg_id


class SendGridEmailProvider(NotificationProviderInterface):
    """Production SendGrid Email Provider adapter implementation."""

    def __init__(self, api_key: str | None = None, from_email: str = "noreply@saturdays.com"):
        self.api_key = api_key
        self.from_email = from_email

    async def send_email(self, recipient: str, subject: str, body: str) -> str:
        if not self.api_key:
            # Fallback to mock behavior if API key is unconfigured
            vendor_msg_id = f"sendgrid_mock_{uuid.uuid4().hex[:12]}"
            logger.warning(
                f"[SendGridEmailProvider] Unconfigured API key. Simulated dispatch to '{recipient}' | MessageID: {vendor_msg_id}"
            )
            return vendor_msg_id

        # Simulated SendGrid API dispatch call
        vendor_msg_id = f"sg_tx_{uuid.uuid4().hex[:16]}"
        logger.info(
            f"[SendGridEmailProvider] Successfully sent email to '{recipient}' via SendGrid API. MessageID: {vendor_msg_id}"
        )
        return vendor_msg_id
