from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import date, datetime
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import quote

from .. import _validate
from .._response import ApiObject, ApiResponse
from .._transport import AsyncTransport, RequestOptions, Transport
from ..errors import PollingTimeoutError

T = TypeVar("T")

MIN_POLL_INTERVAL = 0.5
_SLOW_POLL_AFTER = 30.0
_SLOW_POLL_INTERVAL = 5.0


def path(*segments: str) -> str:
    return "/v1/" + "/".join(quote(s, safe="") for s in segments)


def query(params: dict[str, Any]) -> dict[str, Any]:
    """Validates list filters, formats dates and drops None values."""
    _validate.list_params(params)
    out: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (datetime, date)):
            out[key] = _validate.date_time(value, key)
        else:
            out[key] = value
    return out


def with_key(options: Optional[RequestOptions]) -> RequestOptions:
    if options is None:
        return RequestOptions(idempotency_key=str(uuid.uuid4()))
    if options.idempotency_key is None:
        return options.with_key(str(uuid.uuid4()))
    return options


def to_object(response: ApiResponse) -> ApiObject:
    return ApiObject(response.body if isinstance(response.body, dict) else {}, response)


class SyncResource:
    def __init__(self, transport: Transport, sleep: Callable[[float], None]) -> None:
        self._transport = transport
        self._sleep = sleep

    def _poll(
        self,
        fetch: Callable[[], ApiObject],
        is_terminal: Callable[[dict[str, Any]], bool],
        interval: float,
        timeout: float,
        on_update: Optional[Callable[[ApiObject], None]],
        should_stop: Optional[Callable[[], bool]],
        what: str,
    ) -> ApiObject:
        interval = max(MIN_POLL_INTERVAL, interval)
        waited = 0.0
        last_status: Any = object()
        while True:
            obj = fetch()
            if on_update is not None and obj.get("status") != last_status:
                on_update(obj)
                last_status = obj.get("status")
            if is_terminal(obj):
                return obj
            if should_stop is not None and should_stop():
                raise PollingTimeoutError(f"Polling for {what} was cancelled", obj)
            if waited >= timeout:
                raise PollingTimeoutError(f"{what} did not reach a terminal state within {timeout:g} s", obj)
            delay = max(interval, _SLOW_POLL_INTERVAL) if waited >= _SLOW_POLL_AFTER else interval
            delay = min(delay, timeout - waited)
            self._sleep(delay)
            waited += delay


class AsyncResource:
    def __init__(self, transport: AsyncTransport, sleep: Callable[[float], Awaitable[None]]) -> None:
        self._transport = transport
        self._sleep = sleep

    async def _poll(
        self,
        fetch: Callable[[], Awaitable[ApiObject]],
        is_terminal: Callable[[dict[str, Any]], bool],
        interval: float,
        timeout: float,
        on_update: Optional[Callable[[ApiObject], None]],
        should_stop: Optional[Callable[[], bool]],
        what: str,
    ) -> ApiObject:
        interval = max(MIN_POLL_INTERVAL, interval)
        waited = 0.0
        last_status: Any = object()
        while True:
            obj = await fetch()
            if on_update is not None and obj.get("status") != last_status:
                on_update(obj)
                last_status = obj.get("status")
            if is_terminal(obj):
                return obj
            if should_stop is not None and should_stop():
                raise PollingTimeoutError(f"Polling for {what} was cancelled", obj)
            if waited >= timeout:
                raise PollingTimeoutError(f"{what} did not reach a terminal state within {timeout:g} s", obj)
            delay = max(interval, _SLOW_POLL_INTERVAL) if waited >= _SLOW_POLL_AFTER else interval
            delay = min(delay, timeout - waited)
            await self._sleep(delay)
            waited += delay
