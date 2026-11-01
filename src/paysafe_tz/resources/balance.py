from __future__ import annotations

from typing import Any, Optional

from .._response import ApiObject
from .._transport import RequestOptions
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object


class Balance(SyncResource):
    def get(self, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("GET", path("balance"), None, None, options))

    def transactions(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        """Ledger entries, newest first."""
        params = dict(params or {})
        response = self._transport.request("GET", path("transactions"), query(params), None, options)
        return Page.from_body(
            response.body, response, lambda cursor: self.transactions({**params, "cursor": cursor}, options)
        )


class AsyncBalance(AsyncResource):
    async def get(self, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(await self._transport.request("GET", path("balance"), None, None, options))

    async def transactions(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("transactions"), query(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.transactions({**params, "cursor": cursor}, options)
        )
