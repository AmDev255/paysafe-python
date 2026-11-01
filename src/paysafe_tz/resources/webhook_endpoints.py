from __future__ import annotations

from typing import Any, Optional

from .. import _validate
from .._response import ApiObject
from .._transport import RequestOptions
from ..errors import InvalidRequestError
from ..models import EVENT_TYPES
from ._base import AsyncResource, SyncResource, path, to_object


def _validate_events(params: dict[str, Any]) -> None:
    events = params.get("events")
    if events is None:
        return
    if not isinstance(events, list) or not events:
        raise InvalidRequestError('events must be a non-empty list of event types or ["*"]', "events")
    for event in events:
        if event != "*" and event not in EVENT_TYPES:
            raise InvalidRequestError(f"Unknown event type {event}", "events")


def _validate_create(params: dict[str, Any]) -> None:
    _validate.required(params, ["url"])
    _validate.url(params, "url", 500)
    _validate.string(params, "description", 0, 255)
    _validate_events(params)


def _validate_update(params: dict[str, Any]) -> None:
    _validate.url(params, "url", 500)
    _validate.string(params, "description", 0, 255)
    _validate.enum(params, "status", ["ENABLED", "DISABLED"])
    _validate_events(params)


def _items(body: Any, response: Any) -> list[ApiObject]:
    data = body.get("data") if isinstance(body, dict) else None
    return [ApiObject(item, response) for item in data if isinstance(item, dict)] if isinstance(data, list) else []


class WebhookEndpoints(SyncResource):
    def list(self, options: Optional[RequestOptions] = None) -> list[ApiObject]:
        """Not paginated: a project has a handful of endpoints."""
        response = self._transport.request("GET", path("webhook-endpoints"), None, None, options)
        return _items(response.body, response)

    def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        """The signing secret is only returned here; store it immediately."""
        _validate_create(params)
        return to_object(self._transport.request("POST", path("webhook-endpoints"), {}, params, options))

    def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            self._transport.request("GET", path("webhook-endpoints", _validate.id_(id)), None, None, options)
        )

    def update(self, id: str, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        _validate_update(params)
        return to_object(
            self._transport.request("PATCH", path("webhook-endpoints", _validate.id_(id)), {}, params, options)
        )

    def delete(self, id: str, options: Optional[RequestOptions] = None) -> None:
        self._transport.request("DELETE", path("webhook-endpoints", _validate.id_(id)), None, None, options)


class AsyncWebhookEndpoints(AsyncResource):
    async def list(self, options: Optional[RequestOptions] = None) -> list[ApiObject]:
        response = await self._transport.request("GET", path("webhook-endpoints"), None, None, options)
        return _items(response.body, response)

    async def create(self, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        _validate_create(params)
        return to_object(await self._transport.request("POST", path("webhook-endpoints"), {}, params, options))

    async def get(self, id: str, options: Optional[RequestOptions] = None) -> ApiObject:
        return to_object(
            await self._transport.request("GET", path("webhook-endpoints", _validate.id_(id)), None, None, options)
        )

    async def update(self, id: str, params: dict[str, Any], options: Optional[RequestOptions] = None) -> ApiObject:
        _validate_update(params)
        return to_object(
            await self._transport.request("PATCH", path("webhook-endpoints", _validate.id_(id)), {}, params, options)
        )

    async def delete(self, id: str, options: Optional[RequestOptions] = None) -> None:
        await self._transport.request("DELETE", path("webhook-endpoints", _validate.id_(id)), None, None, options)
