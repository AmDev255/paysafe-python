from __future__ import annotations

from typing import Any, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object


def _validate_list(params: dict[str, Any]) -> dict[str, Any]:
    _validate.string(params, "search", 0, 120)
    return query(params)


class Customers(SyncResource):
    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        params = dict(params or {})
        response = self._transport.request("GET", path("customers"), _validate_list(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(self._transport.request("GET", path("customers", _validate.id_(id)), None, None, options))


class AsyncCustomers(AsyncResource):
    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("customers"), _validate_list(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("GET", path("customers", _validate.id_(id)), None, None, options)
        )
