from __future__ import annotations

from typing import Any, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object
from .payments import MAX_AMOUNT, MIN_AMOUNT

STATUSES = ("active", "paused", "archived")


def _common(params: dict[str, Any]) -> None:
    _validate.string(params, "description", 1, 1000)
    _validate.string(params, "success_message", 1, 255)
    _validate.url(params, "redirect_url", 500)
    _validate.string(params, "logo", 0, 240)
    _validate.string(params, "accent_color", 0, 32)
    if params.get("max_payments") is not None:
        _validate.amount(params["max_payments"], 1, 1_000_000, "max_payments")
    _validate.boolean(params, "collect_name")
    _validate.boolean(params, "collect_email")


def _dates(params: dict[str, Any]) -> dict[str, Any]:
    params = dict(params)
    if "expires_at" in params:
        params["expires_at"] = _validate.date_time(params["expires_at"], "expires_at")
    return params


def _validate_create(params: dict[str, Any]) -> dict[str, Any]:
    _validate.required(params, ["title"])
    _validate.string(params, "title", 2, 120)
    _common(params)
    for field in ("amount", "min_amount", "max_amount"):
        _validate.optional_amount(params, field, MIN_AMOUNT, MAX_AMOUNT)
    _validate.enum(params, "currency", ["TZS"])
    return _dates(params)


def _validate_update(params: dict[str, Any]) -> dict[str, Any]:
    _validate.string(params, "title", 2, 120)
    _validate.enum(params, "status", STATUSES)
    _common(params)
    return _dates(params)


def _validate_list(params: dict[str, Any]) -> dict[str, Any]:
    _validate.enum(params, "status", STATUSES)
    return query(params)


class PaymentLinks(SyncResource):
    def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("POST", path("payment-links"), {}, _validate_create(params), options))

    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        params = dict(params or {})
        response = self._transport.request("GET", path("payment-links"), _validate_list(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("GET", path("payment-links", _validate.id_(id)), None, None, options))

    def update(self, id: str, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        """Pause, resume, archive or edit a link. The amount cannot be changed; archiving is permanent."""
        return to_object(
            self._transport.request(
                "PATCH", path("payment-links", _validate.id_(id)), {}, _validate_update(params), options
            )
        )

    def pause(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return self.update(id, {"status": "paused"}, options)

    def resume(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return self.update(id, {"status": "active"}, options)

    def archive(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return self.update(id, {"status": "archived"}, options)


class AsyncPaymentLinks(AsyncResource):
    async def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("POST", path("payment-links"), {}, _validate_create(params), options)
        )

    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("payment-links"), _validate_list(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("GET", path("payment-links", _validate.id_(id)), None, None, options)
        )

    async def update(self, id: str, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request(
                "PATCH", path("payment-links", _validate.id_(id)), {}, _validate_update(params), options
            )
        )

    async def pause(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return await self.update(id, {"status": "paused"}, options)

    async def resume(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return await self.update(id, {"status": "active"}, options)

    async def archive(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return await self.update(id, {"status": "archived"}, options)
