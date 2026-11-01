from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Optional
from urllib.parse import quote

import httpx

from . import _validate
from ._response import ApiResponse, build_response
from .errors import (
    ApiConnectionError,
    ApiError,
    ApiTimeoutError,
    InvalidRequestError,
    ResponseTooLargeError,
    map_api_error,
)

INITIAL_BACKOFF_MS = 500
MAX_BACKOFF_MS = 8000
IN_PROGRESS_SLEEP_MS = 1000
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

LogRecord = dict[str, Any]


@dataclass(frozen=True)
class RequestOptions:
    idempotency_key: Optional[str] = None
    request_id: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.idempotency_key is not None:
            _validate.idempotency_key(self.idempotency_key)
        if self.request_id is not None:
            _validate.request_id(self.request_id)
        if self.max_retries is not None and (not isinstance(self.max_retries, int) or self.max_retries < 0):
            raise InvalidRequestError("max_retries must be zero or more")
        if self.timeout is not None and not self.timeout > 0:
            raise InvalidRequestError("timeout must be positive")
        _validate.headers(self.headers)

    def with_key(self, key: str) -> RequestOptions:
        return RequestOptions(key, self.request_id, self.timeout, self.max_retries, self.headers)


def query_string(query: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, datetime):
            text = value.isoformat() if value.tzinfo is not None else value.isoformat() + "Z"
        elif isinstance(value, date):
            text = value.isoformat()
        else:
            text = str(value)
        parts.append(f"{quote(str(key), safe='')}={quote(text, safe='')}")
    return "" if not parts else "?" + "&".join(parts)


def encode_body(body: dict[str, Any]) -> bytes:
    def default(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat() if value.tzinfo is not None else value.isoformat() + "Z"
        if isinstance(value, date):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    return json.dumps(body, ensure_ascii=False, default=default).encode("utf-8")


def error_from_response(response: ApiResponse) -> ApiError:
    error = response.body.get("error") if isinstance(response.body, dict) else None
    if isinstance(error, dict):
        raw_code = error.get("code")
        code: str = raw_code if isinstance(raw_code, str) else "unknown"
        return map_api_error(
            response.status,
            code,
            message=error.get("message") if isinstance(error.get("message"), str) else "Request failed",
            request_id=error.get("request_id") if isinstance(error.get("request_id"), str) else response.request_id,
            param=error.get("param") if isinstance(error.get("param"), str) else None,
            details=error.get("details") if isinstance(error.get("details"), dict) else None,
            doc_url=error.get("doc_url") if isinstance(error.get("doc_url"), str) else None,
            headers=response.headers,
            retry_after=response.retry_after,
            rate_limit=response.rate_limit,
        )
    return map_api_error(
        response.status,
        "unknown",
        message=f"HTTP {response.status} from the PaySafe API",
        request_id=response.request_id,
        details=None if response.raw_body == "" else {"raw": response.raw_body[:4096]},
        headers=response.headers,
        retry_after=response.retry_after,
        rate_limit=response.rate_limit,
    )


class _Base:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        api_version: Optional[str],
        user_agent: str,
        logger: Optional[Callable[[LogRecord], None]],
        rng: Callable[[], float],
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._api_version = api_version
        self._user_agent = user_agent
        self._logger = logger
        self._rng = rng

    def _prepare(
        self, method: str, path: str, query: dict[str, Any], body: Optional[dict[str, Any]], options: RequestOptions
    ) -> tuple[str, dict[str, str], Optional[bytes], bool, int]:
        url = self._base_url + path + query_string(query)
        encoded = None if body is None else encode_body(body)
        if encoded is not None:
            _validate.body_size(encoded)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if self._api_version:
            headers["PaySafe-Version"] = self._api_version
        if options.idempotency_key is not None:
            headers["Idempotency-Key"] = options.idempotency_key
        if options.request_id is not None:
            headers["X-Request-ID"] = options.request_id
        headers.update(options.headers)
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        retryable = method in ("GET", "DELETE", "PATCH") or options.idempotency_key is not None
        max_attempts = 1 + (options.max_retries if options.max_retries is not None else self._max_retries)
        return url, headers, encoded, retryable, max_attempts

    def _backoff_ms(self, attempt: int) -> int:
        ceiling = min(MAX_BACKOFF_MS, INITIAL_BACKOFF_MS * 2 ** (attempt - 1))
        return int(self._rng() * (ceiling + 1))

    def _retry_delay_ms(self, error: ApiError, retryable: bool, attempt: int) -> Optional[int]:
        if error.code == "idempotency_in_progress":
            return IN_PROGRESS_SLEEP_MS
        if error.status in (429, 503):
            return error.retry_after * 1000 if error.retry_after is not None else self._backoff_ms(attempt)
        if error.status >= 500 and error.code != "provider_error" and retryable:
            return self._backoff_ms(attempt)
        return None

    def _log(
        self, method: str, path: str, status: Optional[int], attempt: int, started: float, note: Optional[str]
    ) -> None:
        if self._logger is None:
            return
        self._logger(
            {
                "method": method,
                "path": path,
                "status": status,
                "attempt": attempt,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "request_id": note if status is not None else None,
                "error": note if status is None else None,
            }
        )

    @staticmethod
    def _to_response(raw: httpx.Response, idempotency_key: Optional[str]) -> ApiResponse:
        length = raw.headers.get("content-length")
        if length is not None and length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
            raise ResponseTooLargeError("Response body exceeds the 16 MB limit")
        content = raw.content
        if len(content) > MAX_RESPONSE_BYTES:
            raise ResponseTooLargeError("Response body exceeds the 16 MB limit")
        headers = {k.lower(): v for k, v in raw.headers.items()}
        return build_response(raw.status_code, headers, content.decode("utf-8", errors="replace"), idempotency_key)

    @staticmethod
    def _redirect_error(response: ApiResponse) -> ApiError:
        return ApiError(
            response.status,
            "unexpected_redirect",
            "The API answered with a redirect, which this SDK never follows",
            request_id=response.request_id,
            headers=response.headers,
        )

    @staticmethod
    def _connection_error(exc: Exception) -> ApiConnectionError:
        if isinstance(exc, httpx.TimeoutException):
            return ApiTimeoutError(f"Request to PaySafe timed out: {exc}")
        return ApiConnectionError(f"Could not reach PaySafe: {exc}")


class Transport(_Base):
    def __init__(
        self,
        *,
        client: httpx.Client,
        sleep: Callable[[float], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._client = client
        self._sleep = sleep

    def request(
        self,
        method: str,
        path: str,
        query: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> ApiResponse:
        options = options or RequestOptions()
        url, headers, encoded, retryable, max_attempts = self._prepare(method, path, query or {}, body, options)
        attempt = 0
        while True:
            attempt += 1
            started = time.monotonic()
            try:
                raw = self._client.request(
                    method, url, headers=headers, content=encoded, timeout=options.timeout or self._timeout
                )
                response = self._to_response(raw, options.idempotency_key)
            except ResponseTooLargeError:
                raise
            except httpx.HTTPError as exc:
                error = self._connection_error(exc)
                self._log(method, path, None, attempt, started, str(error))
                if not retryable or attempt >= max_attempts:
                    raise error from exc
                self._sleep(self._backoff_ms(attempt) / 1000)
                continue
            self._log(method, path, response.status, attempt, started, response.request_id)
            if response.status < 300:
                return response
            if response.status < 400:
                raise self._redirect_error(response)
            api_error = error_from_response(response)
            delay = self._retry_delay_ms(api_error, retryable, attempt)
            if delay is None or attempt >= max_attempts:
                raise api_error
            self._sleep(delay / 1000)


class AsyncTransport(_Base):
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        sleep: Callable[[float], Awaitable[None]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._client = client
        self._sleep = sleep

    async def request(
        self,
        method: str,
        path: str,
        query: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> ApiResponse:
        options = options or RequestOptions()
        url, headers, encoded, retryable, max_attempts = self._prepare(method, path, query or {}, body, options)
        attempt = 0
        while True:
            attempt += 1
            started = time.monotonic()
            try:
                raw = await self._client.request(
                    method, url, headers=headers, content=encoded, timeout=options.timeout or self._timeout
                )
                response = self._to_response(raw, options.idempotency_key)
            except ResponseTooLargeError:
                raise
            except httpx.HTTPError as exc:
                error = self._connection_error(exc)
                self._log(method, path, None, attempt, started, str(error))
                if not retryable or attempt >= max_attempts:
                    raise error from exc
                await self._sleep(self._backoff_ms(attempt) / 1000)
                continue
            self._log(method, path, response.status, attempt, started, response.request_id)
            if response.status < 300:
                return response
            if response.status < 400:
                raise self._redirect_error(response)
            api_error = error_from_response(response)
            delay = self._retry_delay_ms(api_error, retryable, attempt)
            if delay is None or attempt >= max_attempts:
                raise api_error
            await self._sleep(delay / 1000)


def default_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


async def default_async_sleep(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


default_rng: Callable[[], float] = random.random
