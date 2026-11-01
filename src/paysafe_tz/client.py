from __future__ import annotations

import os
import platform
import re
from collections.abc import Awaitable
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

import httpx

from . import _validate
from ._response import ApiResponse
from ._transport import (
    AsyncTransport,
    LogRecord,
    RequestOptions,
    Transport,
    default_async_sleep,
    default_rng,
    default_sleep,
)
from ._version import VERSION
from .errors import ConfigurationError
from .resources import (
    AsyncBalance,
    AsyncControlNumbers,
    AsyncCustomers,
    AsyncEvents,
    AsyncPaymentLinks,
    AsyncPayments,
    AsyncRefunds,
    AsyncTransfers,
    AsyncWebhookEndpoints,
    Balance,
    ControlNumbers,
    Customers,
    Events,
    PaymentLinks,
    Payments,
    Refunds,
    Transfers,
    WebhookEndpoints,
)

DEFAULT_BASE_URL = "https://api.paysafe.co.tz"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 4


def environment_from_key(api_key: str) -> str:
    if api_key.startswith("paysafe_test_"):
        return "test"
    if api_key.startswith("paysafe_live_"):
        return "live"
    raise ConfigurationError("API key must start with paysafe_test_ or paysafe_live_")


def _settings(
    api_key: Optional[str],
    base_url: Optional[str],
    timeout: float,
    max_retries: int,
    allow_insecure_http: bool,
    user_agent_suffix: Optional[str],
) -> tuple[str, str, str, str]:
    api_key = api_key or os.environ.get("PAYSAFE_SECRET_KEY") or None
    if not api_key:
        raise ConfigurationError("No API key given and PAYSAFE_SECRET_KEY is not set")
    if not re.match(r"^[A-Za-z0-9_]+\Z", api_key):
        raise ConfigurationError("API key contains invalid characters")
    environment = environment_from_key(api_key)

    base_url = base_url or os.environ.get("PAYSAFE_BASE_URL") or DEFAULT_BASE_URL
    if re.search(r"[\s\x00-\x1F\x7F]", base_url):
        raise ConfigurationError("baseUrl contains whitespace or control characters")
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    parts = urlsplit(base_url)
    if not parts.scheme or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ConfigurationError("base_url must be an absolute URL without credentials, query or fragment")
    if parts.scheme != "https" and not (
        parts.scheme == "http" and (allow_insecure_http or _validate.is_loopback(parts.hostname))
    ):
        raise ConfigurationError(
            "base_url must use https (plain http is only allowed for localhost or with allow_insecure_http)"
        )
    if not timeout > 0:
        raise ConfigurationError("timeout must be positive")
    if not isinstance(max_retries, int) or max_retries < 0:
        raise ConfigurationError("max_retries must be zero or more")
    if user_agent_suffix is not None and re.search(r"[\x00-\x1F\x7F]", user_agent_suffix):
        raise ConfigurationError("user_agent_suffix contains control characters")
    user_agent = f"paysafe-python/{VERSION} (Python {platform.python_version()})"
    if user_agent_suffix:
        user_agent += " " + user_agent_suffix
    return api_key, base_url, environment, user_agent


class PaySafe:
    """Synchronous client. Use it as a context manager or call close() when done."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        api_version: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        logger: Optional[Callable[[LogRecord], None]] = None,
        user_agent_suffix: Optional[str] = None,
        allow_insecure_http: bool = False,
        sleep: Callable[[float], None] = default_sleep,
        rng: Callable[[], float] = default_rng,
    ) -> None:
        key, url, environment, user_agent = _settings(
            api_key, base_url, timeout, max_retries, allow_insecure_http, user_agent_suffix
        )
        self.environment = environment
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout, follow_redirects=False, verify=True)
        self._transport = Transport(
            client=self._http,
            sleep=sleep,
            api_key=key,
            base_url=url,
            timeout=timeout,
            max_retries=max_retries,
            api_version=api_version,
            user_agent=user_agent,
            logger=logger,
            rng=rng,
        )
        self.payments = Payments(self._transport, sleep)
        self.payment_links = PaymentLinks(self._transport, sleep)
        self.control_numbers = ControlNumbers(self._transport, sleep)
        self.refunds = Refunds(self._transport, sleep)
        self.balance = Balance(self._transport, sleep)
        self.customers = Customers(self._transport, sleep)
        self.transfers = Transfers(self._transport, sleep)
        self.webhook_endpoints = WebhookEndpoints(self._transport, sleep)
        self.events = Events(self._transport, sleep)

    def request(
        self,
        method: str,
        path: str,
        query: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> ApiResponse:
        """Low-level escape hatch: any request under /v1 with the decoded response."""
        return self._transport.request(method.upper(), "/" + path.lstrip("/"), query, body, options)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> PaySafe:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AsyncPaySafe:
    """Asyncio client with the same surface as PaySafe; every method is awaitable."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        api_version: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        logger: Optional[Callable[[LogRecord], None]] = None,
        user_agent_suffix: Optional[str] = None,
        allow_insecure_http: bool = False,
        sleep: Callable[[float], Awaitable[None]] = default_async_sleep,
        rng: Callable[[], float] = default_rng,
    ) -> None:
        key, url, environment, user_agent = _settings(
            api_key, base_url, timeout, max_retries, allow_insecure_http, user_agent_suffix
        )
        self.environment = environment
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout, follow_redirects=False, verify=True)
        self._transport = AsyncTransport(
            client=self._http,
            sleep=sleep,
            api_key=key,
            base_url=url,
            timeout=timeout,
            max_retries=max_retries,
            api_version=api_version,
            user_agent=user_agent,
            logger=logger,
            rng=rng,
        )
        self.payments = AsyncPayments(self._transport, sleep)
        self.payment_links = AsyncPaymentLinks(self._transport, sleep)
        self.control_numbers = AsyncControlNumbers(self._transport, sleep)
        self.refunds = AsyncRefunds(self._transport, sleep)
        self.balance = AsyncBalance(self._transport, sleep)
        self.customers = AsyncCustomers(self._transport, sleep)
        self.transfers = AsyncTransfers(self._transport, sleep)
        self.webhook_endpoints = AsyncWebhookEndpoints(self._transport, sleep)
        self.events = AsyncEvents(self._transport, sleep)

    async def request(
        self,
        method: str,
        path: str,
        query: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> ApiResponse:
        return await self._transport.request(method.upper(), "/" + path.lstrip("/"), query, body, options)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncPaySafe:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
