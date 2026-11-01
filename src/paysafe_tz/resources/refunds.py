from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..models import is_refund_terminal
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object, with_key

REASONS = ("requested_by_customer", "duplicate", "fraudulent", "other")
STATUSES = ("pending", "processing", "succeeded", "failed", "rejected")


def _validate_create(params: dict[str, Any]) -> None:
    _validate.required(params, ["payment"])
    _validate.id_(params["payment"], "payment")
    _validate.optional_amount(params, "amount", 1, sys.maxsize)
    _validate.enum(params, "reason", REASONS)
    _validate.metadata(params)


def _validate_list(params: dict[str, Any]) -> dict[str, Any]:
    _validate.enum(params, "status", STATUSES)
    if params.get("payment") is not None:
        _validate.id_(params["payment"], "payment")
    return query(params)


class Refunds(SyncResource):
    def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        """Refunds a succeeded payment (202 Accepted). Omit amount to refund the remaining balance."""
        _validate_create(params)
        return to_object(self._transport.request("POST", path("refunds"), {}, params, with_key(options)))

    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        params = dict(params or {})
        response = self._transport.request("GET", path("refunds"), _validate_list(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("GET", path("refunds", _validate.id_(id)), None, None, options))

    def wait_for_terminal(
        self,
        id: str,
        interval: float = 1.0,
        timeout: float = 60.0,
        on_update: Optional[Callable[[ApiObject], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> ApiObject:
        _validate.id_(id)
        return self._poll(
            lambda: self.get(id), is_refund_terminal, interval, timeout, on_update, should_stop, f"refund {id}"
        )


class AsyncRefunds(AsyncResource):
    async def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        _validate_create(params)
        return to_object(await self._transport.request("POST", path("refunds"), {}, params, with_key(options)))

    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("refunds"), _validate_list(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(await self._transport.request("GET", path("refunds", _validate.id_(id)), None, None, options))

    async def wait_for_terminal(
        self,
        id: str,
        interval: float = 1.0,
        timeout: float = 60.0,
        on_update: Optional[Callable[[ApiObject], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> ApiObject:
        _validate.id_(id)
        return await self._poll(
            lambda: self.get(id), is_refund_terminal, interval, timeout, on_update, should_stop, f"refund {id}"
        )
