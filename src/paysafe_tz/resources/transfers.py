from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..models import is_transfer_terminal
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object, with_key


def _validate_create(params: dict[str, Any]) -> None:
    _validate.required(params, ["to", "amount"])
    _validate.string(params, "to", 3, 31)
    _validate.amount(params["amount"], 1, sys.maxsize)
    _validate.enum(params, "currency", ["TZS"])
    _validate.string(params, "note", 0, 140)


class Transfers(SyncResource):
    def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        """Moves money from this project's available balance to another PaySafe project (201)."""
        _validate_create(params)
        return to_object(self._transport.request("POST", path("transfers"), {}, params, with_key(options)))

    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        params = dict(params or {})
        response = self._transport.request("GET", path("transfers"), query(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("GET", path("transfers", _validate.id_(id)), None, None, options))

    def wait_for_terminal(
        self,
        id: str,
        interval: float = 2.0,
        timeout: float = 120.0,
        on_update: Optional[Callable[[ApiObject], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> ApiObject:
        _validate.id_(id)
        return self._poll(
            lambda: self.get(id), is_transfer_terminal, interval, timeout, on_update, should_stop, f"transfer {id}"
        )


class AsyncTransfers(AsyncResource):
    async def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        _validate_create(params)
        return to_object(await self._transport.request("POST", path("transfers"), {}, params, with_key(options)))

    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("transfers"), query(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("GET", path("transfers", _validate.id_(id)), None, None, options)
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
            lambda: self.get(id), is_transfer_terminal, interval, timeout, on_update, should_stop, f"transfer {id}"
        )
