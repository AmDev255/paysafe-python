from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Sequence
from typing import Any, Optional, Union

from ._response import ApiObject
from .errors import SignatureVerificationError

DEFAULT_TOLERANCE_SECONDS = 300
SIGNATURE_HEADER = "PaySafe-Signature"
MAX_HEADER_BYTES = 4096
MAX_PAYLOAD_BYTES = 1024 * 1024

Payload = Union[str, bytes, bytearray]


def _to_bytes(payload: Payload) -> bytes:
    return payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)


def sign(secret: str, payload: Payload, timestamp: Optional[int] = None) -> str:
    """Builds a PaySafe-Signature value. Intended for tests."""
    t = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode("utf-8"), f"{t}.".encode() + _to_bytes(payload), hashlib.sha256).hexdigest()
    return f"t={t},v1={digest}"


def _check(
    secret: Union[str, Sequence[str]],
    payload: Payload,
    header: Optional[str],
    tolerance: int,
    now: Optional[int],
) -> None:
    if header is None or header.strip() == "":
        raise SignatureVerificationError(
            SignatureVerificationError.MISSING_HEADER, "PaySafe-Signature header is missing"
        )
    body = _to_bytes(payload)
    if len(header) > MAX_HEADER_BYTES or len(body) > MAX_PAYLOAD_BYTES:
        raise SignatureVerificationError(
            SignatureVerificationError.MALFORMED_HEADER, "Webhook header or payload is too large"
        )
    timestamp: Optional[str] = None
    signatures: list[str] = []
    for part in header.split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            continue
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value.strip().lower())
    if timestamp is None or not timestamp.isdigit() or not signatures:
        raise SignatureVerificationError(
            SignatureVerificationError.MALFORMED_HEADER, "PaySafe-Signature header is malformed"
        )
    t = int(timestamp)
    current = int(time.time()) if now is None else now
    if abs(current - t) > tolerance:
        raise SignatureVerificationError(
            SignatureVerificationError.TIMESTAMP_OUTSIDE_TOLERANCE, "Webhook timestamp is outside the tolerance window"
        )
    secrets = [secret] if isinstance(secret, str) else list(secret)
    for candidate in secrets:
        expected = hmac.new(candidate.encode("utf-8"), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
        for signature in signatures:
            if hmac.compare_digest(expected, signature):
                return
    raise SignatureVerificationError(SignatureVerificationError.SIGNATURE_MISMATCH, "Webhook signature does not match")


def verify_signature(
    secret: Union[str, Sequence[str]],
    payload: Payload,
    header: Optional[str],
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[int] = None,
) -> bool:
    """True when the raw payload was signed by one of the secrets within the tolerance window. Never raises."""
    try:
        _check(secret, payload, header, tolerance, now)
    except SignatureVerificationError:
        return False
    return True


def construct_event(
    secret: Union[str, Sequence[str]],
    payload: Payload,
    header: Optional[str],
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[int] = None,
) -> ApiObject:
    """Verifies the delivery and returns the event. Raises SignatureVerificationError with a reason."""
    _check(secret, payload, header, tolerance, now)
    try:
        decoded: Any = json.loads(_to_bytes(payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SignatureVerificationError(
            SignatureVerificationError.INVALID_PAYLOAD, "Webhook payload is not valid JSON"
        ) from None
    if (
        not isinstance(decoded, dict)
        or not isinstance(decoded.get("id"), str)
        or not isinstance(decoded.get("type"), str)
    ):
        raise SignatureVerificationError(
            SignatureVerificationError.INVALID_PAYLOAD, "Webhook payload is not an event object"
        )
    return ApiObject(decoded)
