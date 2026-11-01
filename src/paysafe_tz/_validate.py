from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Optional
from urllib.parse import urlsplit

from .errors import InvalidRequestError

MAX_BODY_BYTES = 65536
MAX_METADATA_BYTES = 8192

_PROTECTED_HEADERS = {"authorization", "host", "content-length", "transfer-encoding", "connection"}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}\Z")
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,100}\Z")
_HEADER_VALUE_BAD = re.compile(r"[\x00-\x08\x0A-\x1F\x7F]")
_PRINTABLE = re.compile(r"^[\x20-\x7E]+\Z")
_CURSOR = re.compile(r"^[\x21-\x7E]+\Z")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}\Z")
_PHONE = re.compile(r"^\+255\d{9}\Z")
_QUERY_KEY = re.compile(r"^[A-Za-z0-9_]{1,40}\Z")
_CONTROL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2}))?\Z")
_LOOPBACK = {"localhost", "127.0.0.1", "::1", "[::1]", "host.docker.internal"}


def idempotency_key(key: str) -> None:
    if not isinstance(key, str) or not 1 <= len(key) <= 255 or not _PRINTABLE.match(key):
        raise InvalidRequestError("Idempotency-Key must be 1 to 255 printable ASCII characters")


def request_id(value: str) -> None:
    if not isinstance(value, str) or not _REQUEST_ID.match(value):
        raise InvalidRequestError("X-Request-ID must be 8 to 64 characters of A-Z a-z 0-9 . _ -")


def id_(value: Any, name: str = "id") -> str:
    """Identifiers go into URL paths; anything outside the id alphabet is rejected."""
    if not isinstance(value, str) or not _ID.match(value):
        raise InvalidRequestError(f"{name} must be 1 to 64 characters of A-Z a-z 0-9 _ -", name)
    return value


def headers(values: Optional[dict[str, str]]) -> None:
    if not values:
        return
    for name, value in values.items():
        if not isinstance(name, str) or not _HEADER_NAME.match(name):
            raise InvalidRequestError("Header names may only contain letters, digits and dashes")
        if name.lower() in _PROTECTED_HEADERS:
            raise InvalidRequestError(f"The {name} header cannot be overridden")
        if not isinstance(value, str) or _HEADER_VALUE_BAD.search(value) or len(value) > 4096:
            raise InvalidRequestError(f"Header {name} has an invalid value")


def required(params: dict[str, Any], fields: Sequence[str]) -> None:
    for field in fields:
        value: Any = params
        for segment in field.split("."):
            value = value.get(segment) if isinstance(value, dict) else None
        if value is None or value == "":
            raise InvalidRequestError(f"{field} is required", field)


def phone(value: Any, field: str = "customer.phone") -> None:
    if not isinstance(value, str) or not _PHONE.match(value):
        raise InvalidRequestError(f"{field} must be an E.164 Tanzanian number (+255 followed by nine digits)", field)


def amount(value: Any, minimum: int, maximum: int, field: str = "amount") -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidRequestError(f"{field} must be an integer between {minimum} and {maximum}", field)


def optional_amount(params: dict[str, Any], field: str, minimum: int, maximum: int) -> None:
    if params.get(field) is not None:
        amount(params[field], minimum, maximum, field)


def enum(params: dict[str, Any], field: str, allowed: Sequence[str]) -> None:
    value = params.get(field)
    if value is None:
        return
    if not isinstance(value, str) or value not in allowed:
        raise InvalidRequestError(f"{field} must be one of {', '.join(allowed)}", field)


def string(params: dict[str, Any], field: str, minimum: int, maximum: int) -> None:
    value = params.get(field)
    if value is None:
        return
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or _CONTROL.search(value):
        raise InvalidRequestError(f"{field} must be a string of {minimum} to {maximum} characters", field)


def boolean(params: dict[str, Any], field: str) -> None:
    value = params.get(field)
    if value is not None and not isinstance(value, bool):
        raise InvalidRequestError(f"{field} must be a boolean", field)


def list_params(params: dict[str, Any]) -> None:
    limit = params.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100):
        raise InvalidRequestError("limit must be an integer between 1 and 100", "limit")
    cursor = params.get("cursor")
    if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 200 or not _CURSOR.match(cursor)):
        raise InvalidRequestError("cursor must be an opaque value returned by a previous list call", "cursor")
    for key, value in params.items():
        if not isinstance(key, str) or not _QUERY_KEY.match(key):
            raise InvalidRequestError("Query parameter names must be alphanumeric")
        if value is None or isinstance(value, (bool, int, datetime, date)):
            continue
        if not isinstance(value, str) or len(value) > 500 or re.search(r"[\x00-\x1F\x7F]", value):
            raise InvalidRequestError(f"{key} has an invalid value", key)


def metadata(params: dict[str, Any], field: str = "metadata") -> None:
    value = params.get(field)
    if value is None:
        return
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise InvalidRequestError(f"{field} must be an object with string keys", field)
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_METADATA_BYTES:
        raise InvalidRequestError(f"{field} must encode to at most {MAX_METADATA_BYTES} bytes of JSON", field)


def is_loopback(host: str) -> bool:
    return host.lower() in _LOOPBACK


def url(params: dict[str, Any], field: str, max_length: int = 500) -> None:
    value = params.get(field)
    if value is None:
        return
    if not isinstance(value, str) or len(value) > max_length or re.search(r"[\s\x00-\x1F\x7F]", value):
        raise InvalidRequestError(f"{field} must be a URL of at most {max_length} characters", field)
    parts = urlsplit(value)
    if not parts.scheme or not parts.hostname:
        raise InvalidRequestError(f"{field} must be an absolute URL", field)
    if parts.scheme != "https" and not (parts.scheme == "http" and is_loopback(parts.hostname)):
        raise InvalidRequestError(f"{field} must use https", field)


def body_size(encoded: bytes) -> None:
    if len(encoded) > MAX_BODY_BYTES:
        raise InvalidRequestError(f"Request body exceeds the {MAX_BODY_BYTES} byte limit")


def date_time(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        text = value.isoformat()
        return text if value.tzinfo is not None else text + "Z"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and _DATETIME.match(value):
        return value
    raise InvalidRequestError(f"{field} must be an RFC 3339 timestamp, a YYYY-MM-DD date, a date or a datetime", field)
