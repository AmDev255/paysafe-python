from __future__ import annotations

import json
import time
from email.utils import formatdate

import pytest

from paysafe_tz import (
    ApiError,
    AuthenticationError,
    ConflictError,
    FeatureDisabledError,
    IdempotencyConflictError,
    IdempotencyInProgressError,
    InsufficientFundsError,
    InternalError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)
from paysafe_tz._response import build_response, retry_after_from_headers
from paysafe_tz._transport import error_from_response

CASES = [
    (400, "validation_error", ValidationError, False),
    (401, "authentication_error", AuthenticationError, False),
    (403, "permission_error", PermissionDeniedError, False),
    (403, "feature_disabled", FeatureDisabledError, False),
    (404, "not_found", NotFoundError, False),
    (402, "insufficient_funds", InsufficientFundsError, False),
    (409, "conflict", ConflictError, False),
    (409, "idempotency_conflict", IdempotencyConflictError, False),
    (409, "idempotency_in_progress", IdempotencyInProgressError, True),
    (409, "invalid_state", InvalidStateError, False),
    (429, "rate_limited", RateLimitError, True),
    (502, "provider_error", ProviderError, False),
    (503, "provider_unavailable", ProviderUnavailableError, True),
    (503, "service_unavailable", ServiceUnavailableError, True),
    (500, "internal_error", InternalError, True),
]


@pytest.mark.parametrize(("status", "code", "cls", "retryable"), CASES)
def test_every_documented_code_maps_to_its_class(status: int, code: str, cls: type[ApiError], retryable: bool) -> None:
    body = {
        "error": {
            "code": code,
            "message": "m",
            "request_id": "req_1",
            "param": "amount",
            "details": {"scope": "api:key"},
            "doc_url": f"https://paysafe.co.tz/docs/errors#{code}",
        }
    }
    response = build_response(status, {"x-request-id": "req_1", "retry-after": "3"}, json.dumps(body), None)
    error = error_from_response(response)
    assert isinstance(error, cls)
    assert (error.status, error.code, error.request_id, error.param) == (status, code, "req_1", "amount")
    assert error.details == {"scope": "api:key"}
    assert error.retry_after == 3
    assert error.is_retryable is retryable
    assert code in str(error)


def test_unknown_code_falls_back_to_status() -> None:
    a = error_from_response(
        build_response(404, {}, json.dumps({"error": {"code": "brand_new", "message": "x", "request_id": "r"}}), None)
    )
    assert isinstance(a, NotFoundError) and a.code == "brand_new"
    b = error_from_response(
        build_response(418, {}, json.dumps({"error": {"code": "teapot", "message": "x", "request_id": "r"}}), None)
    )
    assert type(b) is ApiError
    c = error_from_response(build_response(500, {"x-request-id": "req_h"}, "oops", None))
    assert isinstance(c, InternalError) and c.request_id == "req_h" and c.code == "unknown"


def test_retry_after_accepts_http_dates() -> None:
    assert retry_after_from_headers({"retry-after": "7"}) == 7
    now = time.time()
    assert retry_after_from_headers({"retry-after": formatdate(now + 120, usegmt=True)}, now) in (120, 121)
    assert retry_after_from_headers({}) is None


def test_helpers_on_specific_errors() -> None:
    p = error_from_response(
        build_response(
            403,
            {},
            json.dumps(
                {
                    "error": {
                        "code": "permission_error",
                        "message": "x",
                        "request_id": "r",
                        "details": {"code": "ip_not_allowed", "ip": "2a02::1"},
                    }
                }
            ),
            None,
        )
    )
    assert isinstance(p, PermissionDeniedError) and p.is_ip_not_allowed and p.observed_ip == "2a02::1"
    f = error_from_response(
        build_response(
            402,
            {},
            json.dumps(
                {
                    "error": {
                        "code": "insufficient_funds",
                        "message": "x",
                        "request_id": "r",
                        "details": {"available": 10, "requested": 20},
                    }
                }
            ),
            None,
        )
    )
    assert isinstance(f, InsufficientFundsError) and f.available == 10 and f.requested == 20
