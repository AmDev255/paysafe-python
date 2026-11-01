from __future__ import annotations

from typing import Any, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..models import EVENT_TYPES
from ..page import AsyncPage, Page
from ._base import AsyncResource, SyncResource, path, query, to_object


def _validate_list(params: dict[str, Any]) -> dict[str, Any]:
    params = dict(params)
    if "from_" in params:
        params["from"] = params.pop("from_")
    _validate.enum(params, "type", EVENT_TYPES)
    for field in ("from", "to"):
        if field in params:
            params[field] = _validate.date_time(params[field], field)
    if params.get("resourceId") is not None:
        _validate.id_(params["resourceId"], "resourceId")
    return query(params)


class Events(SyncResource):
    def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> Page[ApiObject]:
        """Filters: limit, cursor, type, from_ (or from), to, resourceId."""
        params = dict(params or {})
        response = self._transport.request("GET", path("events"), _validate_list(params), None, options)
        return Page.from_body(response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        """The event plus every delivery attempt to your endpoints."""
        return to_object(self._transport.request("GET", path("events", _validate.id_(id)), None, None, options))


class AsyncEvents(AsyncResource):
    async def list(
        self, params: Optional[dict[str, Any]] = None, options: Optional[RequestOptions] = None
    ) -> AsyncPage[ApiObject]:
        params = dict(params or {})
        response = await self._transport.request("GET", path("events"), _validate_list(params), None, options)
        return AsyncPage.from_body(
            response.body, response, lambda cursor: self.list({**params, "cursor": cursor}, options)
        )

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(await self._transport.request("GET", path("events", _validate.id_(id)), None, None, options))
