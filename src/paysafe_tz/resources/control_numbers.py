from __future__ import annotations

from typing import Any, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..errors import InvalidRequestError
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object

STATUSES = ("active", "paid", "expired", "cancelled")
STATES = ("unpaid", "partial", "paid", "overdue")
MODES = ("full", "instalment")
MAX_AMOUNT = 1_000_000_000_000


def _validate_create(params: dict[str, Any]) -> dict[str, Any]:
    params = dict(params)
    _validate.required(params, ["payer_name", "title", "amount"])
    for field, lo, hi in (
        ("payer_name", 1, 120),
        ("payer_phone", 0, 20),
        ("payer_email", 0, 255),
        ("payer_reference", 0, 120),
        ("title", 1, 150),
        ("description", 0, 500),
        ("reference", 0, 120),
        ("payment_type", 0, 60),
        ("notes", 0, 1000),
        ("image", 0, 240),
    ):
        _validate.string(params, field, lo, hi)
    _validate.enum(params, "mode", MODES)
    _validate.enum(params, "currency", ["TZS"])
    _validate.amount(params["amount"], 1, MAX_AMOUNT)
    _validate.metadata(params)
    if "expires_at" in params:
        params["expires_at"] = _validate.date_time(params["expires_at"], "expires_at")
    instalments = params.get("instalments")
    if instalments is not None:
        if not isinstance(instalments, list) or not instalments:
            raise InvalidRequestError("instalments must be a non-empty list", "instalments")
        cleaned = []
        for i, item in enumerate(instalments):
            if not isinstance(item, dict) or "amount" not in item or "due_at" not in item:
                raise InvalidRequestError(f"instalments[{i}] needs amount and due_at", "instalments")
            _validate.amount(item["amount"], 1, MAX_AMOUNT, f"instalments[{i}].amount")
            due = _validate.date_time(item["due_at"], f"instalments[{i}].due_at")
            if due is None:
                raise InvalidRequestError(f"instalments[{i}].due_at is required", "instalments")
            cleaned.append({"amount": item["amount"], "due_at": due})
        params["instalments"] = cleaned
    return params


def _validate_list(params: dict[str, Any]) -> dict[str, Any]:
    _validate.enum(params, "status", STATUSES)
    _validate.enum(params, "state", STATES)
    _validate.string(params, "q", 0, 80)
    return query(params)


def _validate_reason(reason: str) -> dict[str, Any]:
    body = {"reason": reason}
    _validate.string(body, "reason", 3, 500)
    return body


class ControlNumbers(SyncResource):
    def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        """Issues a 12-digit pay-by-reference number (201). The number itself is assigned by the server."""
        return to_object(
            self._transport.request("POST", path("control-numbers"), {}, _validate_create(params), options)
        )

    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        params = dict(params or {})
        response = self._transport.request("GET", path("control-numbers"), _validate_list(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        """The number with every payment entry recorded against it."""
        return to_object(
            self._transport.request("GET", path("control-numbers", _validate.id_(id)), None, None, options)
        )

    def cancel(self, id: str, reason: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            self._transport.request(
                "POST", path("control-numbers", _validate.id_(id), "cancel"), {}, _validate_reason(reason), options
            )
        )


class AsyncControlNumbers(AsyncResource):
    async def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("POST", path("control-numbers"), {}, _validate_create(params), options)
        )

    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("control-numbers"), _validate_list(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("GET", path("control-numbers", _validate.id_(id)), None, None, options)
        )

    async def cancel(self, id: str, reason: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request(
                "POST", path("control-numbers", _validate.id_(id), "cancel"), {}, _validate_reason(reason), options
            )
        )
