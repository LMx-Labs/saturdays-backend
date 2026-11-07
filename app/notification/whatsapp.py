"""Sending WhatsApp messages through Meta's WhatsApp Business Cloud API.

Only pre-approved *template* messages are sent: that is the only kind WhatsApp lets a business
start. This module just knows how to talk to WhatsApp; deciding whether, when and to whom to send
lives in `whatsapp_service.py`.
"""

import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class WhatsAppSendError(Exception):
    """A message could not be sent. `retryable` says whether trying again later could help."""

    def __init__(
        self, message: str, *, retryable: bool = False, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass(frozen=True)
class TemplateMessage:
    to: str  # digits with country code, e.g. "919876543210"
    template: str
    language: str
    body_params: list[str] = field(default_factory=list)


def clean_param(value: object) -> str:
    """WhatsApp rejects a parameter that is empty, has line breaks or tabs, or has long runs of
    spaces. Make any text safe, and never leave it empty."""
    text = re.sub(r"[\r\n\t]+", " ", str(value if value is not None else ""))
    text = re.sub(r" {4,}", "   ", text).strip()
    return text[:1000] or "-"


class WhatsAppProviderInterface(ABC):
    @abstractmethod
    async def send_template(self, message: TemplateMessage) -> str:
        """Send a template message and return WhatsApp's id for it."""


class MockWhatsAppProvider(WhatsAppProviderInterface):
    """Sends nothing. Remembers what it was asked to send, for development, demos and tests."""

    def __init__(self) -> None:
        self.sent: list[TemplateMessage] = []
        self.fail_with: Exception | None = None

    async def send_template(self, message: TemplateMessage) -> str:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)
        message_id = f"mock_wamid_{uuid.uuid4().hex[:16]}"
        logger.info(
            "[MockWhatsAppProvider] template=%s to=…%s params=%d id=%s",
            message.template,
            message.to[-3:],
            len(message.body_params),
            message_id,
        )
        return message_id


class CloudApiWhatsAppProvider(WhatsAppProviderInterface):
    def __init__(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        api_version: str = "v21.0",
        base_url: str = "https://graph.facebook.com",
        timeout: float = 3.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/{api_version}/{phone_number_id}/messages"
        self._token = access_token
        self._timeout = timeout
        self._client = client

    def _payload(self, message: TemplateMessage) -> dict:
        template: dict = {
            "name": message.template,
            "language": {"code": message.language},
        }
        if message.body_params:
            template["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": clean_param(p)}
                        for p in message.body_params
                    ],
                }
            ]
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.to,
            "type": "template",
            "template": template,
        }

    async def send_template(self, message: TemplateMessage) -> str:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            if self._client is not None:
                response = await self._client.post(
                    self._url, json=self._payload(message), headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        self._url, json=self._payload(message), headers=headers
                    )
        except httpx.TimeoutException as exc:
            raise WhatsAppSendError("WhatsApp timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise WhatsAppSendError(
                f"Could not reach WhatsApp ({type(exc).__name__})", retryable=True
            ) from exc

        if response.status_code >= 400:
            code: str | None = None
            detail = f"HTTP {response.status_code}"
            try:
                error = response.json().get("error", {})
                code = str(error["code"]) if "code" in error else None
                detail = (
                    f"{code or response.status_code}: {error.get('message', detail)}"
                )
            except ValueError:
                pass
            # 5xx and rate limits are worth another try later; a rejected number or template is not.
            retryable = response.status_code >= 500 or response.status_code == 429
            raise WhatsAppSendError(detail, retryable=retryable, code=code)

        try:
            return str(response.json()["messages"][0]["id"])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise WhatsAppSendError("WhatsApp gave no message id") from exc


def build_whatsapp_provider(cfg: Settings) -> WhatsAppProviderInterface | None:
    """The provider the settings ask for, or None if it isn't fully set up (logged, never fatal)."""
    kind = cfg.WHATSAPP_PROVIDER.strip().lower()
    if kind == "mock":
        return MockWhatsAppProvider()
    if kind == "cloud":
        if not cfg.WHATSAPP_PHONE_NUMBER_ID or not cfg.WHATSAPP_ACCESS_TOKEN:
            logger.error(
                "WhatsApp is enabled but WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN is missing"
            )
            return None
        return CloudApiWhatsAppProvider(
            phone_number_id=cfg.WHATSAPP_PHONE_NUMBER_ID,
            access_token=cfg.WHATSAPP_ACCESS_TOKEN,
            api_version=cfg.WHATSAPP_API_VERSION,
            base_url=cfg.WHATSAPP_API_BASE_URL,
            timeout=cfg.WHATSAPP_TIMEOUT_SECONDS,
        )
    logger.error(
        "Unknown WHATSAPP_PROVIDER %r (use 'cloud' or 'mock')", cfg.WHATSAPP_PROVIDER
    )
    return None
