from __future__ import annotations

import json
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Optional


@dataclass(frozen=True)
class RateLimit:
    limit: Optional[int]
    remaining: Optional[int]
    reset: Optional[int]

    @staticmethod
    def from_headers(headers: dict[str, str]) -> Optional[RateLimit]:
        limit = headers.get("x-ratelimit-limit")
        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if limit is None and remaining is None and reset is None:
            return None
        return RateLimit(_int(limit), _int(remaining), _int(reset))


def _int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def retry_after_from_headers(headers: dict[str, str], now: Optional[float] = None) -> Optional[int]:
    value = headers.get("retry-after")
    if value is None:
        return None
    if value.isdigit():
        return int(value)
    try:
        at = parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError):
        return None
    import time

    current = time.time() if now is None else now
    return max(0, int(-(-(at - current) // 1)))


@dataclass(frozen=True)
class ApiResponse:
    status: int
    headers: dict[str, str]
    body: Any
    raw_body: str
    idempotency_key: Optional[str] = None

    @property
    def request_id(self) -> Optional[str]:
        return self.headers.get("x-request-id")

    @property
    def rate_limit(self) -> Optional[RateLimit]:
        return RateLimit.from_headers(self.headers)

    @property
    def idempotent_replayed(self) -> bool:
        return self.headers.get("idempotent-replayed") == "true"

    @property
    def retry_after(self) -> Optional[int]:
        return retry_after_from_headers(self.headers)


def build_response(status: int, headers: dict[str, str], raw_body: str, idempotency_key: Optional[str]) -> ApiResponse:
    body: Any = None
    if raw_body != "":
        try:
            body = json.loads(raw_body)
        except ValueError:
            body = None
    return ApiResponse(status, headers, body, raw_body, idempotency_key)


class ApiObject(dict):  # type: ignore[type-arg]
    """A JSON object from the API, as a dict, plus the response it came from in `last_response`."""

    last_response: Optional[ApiResponse]

    def __init__(self, data: dict[str, Any], last_response: Optional[ApiResponse] = None) -> None:
        super().__init__(data)
        object.__setattr__(self, "last_response", last_response)

    @property
    def request_id(self) -> Optional[str]:
        return self.last_response.request_id if self.last_response else None

    def __getattr__(self, name: str) -> Any:
        # Attribute access mirrors key access for convenience: payment.status == payment["status"].
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None
