from __future__ import annotations

from typing import Any, Callable, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..models import is_payment_terminal
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object, with_key

CHANNELS = ("mpesa", "tigopesa", "airtel", "halopesa")
STATUSES = (
    "created",
    "pending",
    "processing",
    "requires_action",
    "succeeded",
    "failed",
    "cancelled",
    "expired",
    "partially_refunded",
    "refunded",
)
MIN_AMOUNT = 1000
MAX_AMOUNT = 10_000_000


def _validate_create(params: dict[str, Any]) -> None:
    _validate.required(params, ["amount", "customer.phone"])
    _validate.amount(params["amount"], MIN_AMOUNT, MAX_AMOUNT)
    customer = params["customer"]
    _validate.phone(customer.get("phone"))
    _validate.string(customer, "name", 1, 100)
    _validate.string(customer, "email", 3, 255)
    _validate.enum(params, "currency", ["TZS"])
    _validate.enum(params, "channel", CHANNELS)
    _validate.string(params, "reference", 1, 120)
    _validate.string(params, "description", 1, 255)
    _validate.metadata(params)
    if params.get("expires_in") is not None:
        _validate.amount(params["expires_in"], 60, 900, "expires_in")


def _validate_list(params: dict[str, Any]) -> dict[str, Any]:
    _validate.enum(params, "status", STATUSES)
    return query(params)


def _validate_cancel(params: dict[str, Any]) -> None:
    _validate.string(params, "reason", 0, 255)


class Payments(SyncResource):
    def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        """Starts a mobile-money charge (202 Accepted). An Idempotency-Key is generated when none is given."""
        _validate_create(params)
        return to_object(self._transport.request("POST", path("payments"), {}, params, with_key(options)))

    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        params = dict(params or {})
        response = self._transport.request("GET", path("payments"), _validate_list(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("GET", path("payments", _validate.id_(id)), None, None, options))

    def cancel(
        self, id: str, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> ApiObject:
        """Only payments in created or pending can be cancelled. The API requires an Idempotency-Key here."""
        params = dict(params or {})
        _validate_cancel(params)
        return to_object(
            self._transport.request(
                "POST", path("payments", _validate.id_(id), "cancel"), {}, params, with_key(options)
            )
        )

    def wait_for_terminal(
        self,
        id: str,
        interval: float = 2.0,
        timeout: float = 120.0,
        on_update: Optional[Callable[[ApiObject], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> ApiObject:
        """Polls `get` until the payment is terminal."""
        _validate.id_(id)
        return self._poll(
            lambda: self.get(id), is_payment_terminal, interval, timeout, on_update, should_stop, f"payment {id}"
        )


class AsyncPayments(AsyncResource):
    async def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        _validate_create(params)
        return to_object(await self._transport.request("POST", path("payments"), {}, params, with_key(options)))

    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("payments"), _validate_list(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(await self._transport.request("GET", path("payments", _validate.id_(id)), None, None, options))

    async def cancel(
        self, id: str, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> ApiObject:
        params = dict(params or {})
        _validate_cancel(params)
        return to_object(
            await self._transport.request(
                "POST", path("payments", _validate.id_(id), "cancel"), {}, params, with_key(options)
            )
        )

    async def wait_for_terminal(
        self,
        id: str,
        interval: float = 2.0,
        timeout: float = 120.0,
        on_update: Optional[Callable[[ApiObject], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> ApiObject:
        _validate.id_(id)
        return await self._poll(
            lambda: self.get(id), is_payment_terminal, interval, timeout, on_update, should_stop, f"payment {id}"
        )
