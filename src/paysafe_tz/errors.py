from __future__ import annotations

from typing import Any, Optional

from ._response import RateLimit


class PaySafeError(Exception):
    """Base class for every error raised by this SDK."""


class ConfigurationError(PaySafeError):
    pass


class InvalidRequestError(PaySafeError):
    """Rejected locally before any request was sent."""

    def __init__(self, message: str, param: Optional[str] = None) -> None:
        super().__init__(message)
        self.param = param


class ApiConnectionError(PaySafeError):
    """No HTTP response was received."""


class ApiTimeoutError(ApiConnectionError):
    pass


class ResponseTooLargeError(ApiConnectionError):
    pass


class PollingTimeoutError(PaySafeError):
    def __init__(self, message: str, last_seen: Any = None) -> None:
        super().__init__(message)
        self.last_seen = last_seen


class SignatureVerificationError(PaySafeError):
    MISSING_HEADER = "missing_header"
    MALFORMED_HEADER = "malformed_header"
    TIMESTAMP_OUTSIDE_TOLERANCE = "timestamp_outside_tolerance"
    SIGNATURE_MISMATCH = "signature_mismatch"
    INVALID_PAYLOAD = "invalid_payload"

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class ApiError(PaySafeError):
    """Any non-2xx response from the API. Subclasses exist for every documented error code."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        request_id: Optional[str] = None,
        param: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        doc_url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        retry_after: Optional[int] = None,
        rate_limit: Optional[RateLimit] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.param = param
        self.details = details
        self.doc_url = doc_url
        self.headers = headers or {}
        self.retry_after = retry_after
        self.rate_limit = rate_limit

    @property
    def is_retryable(self) -> bool:
        if self.status in (429, 503) or self.code == "idempotency_in_progress":
            return True
        return self.status >= 500 and self.code != "provider_error"

    def __str__(self) -> str:
        return f"{self.code} ({self.status}) {self.message} [{self.request_id or 'no request id'}]"


class ValidationError(ApiError):
    pass


class AuthenticationError(ApiError):
    pass


class PermissionDeniedError(ApiError):
    @property
    def is_ip_not_allowed(self) -> bool:
        code = (self.details or {}).get("code")
        return code in ("ip_not_allowed", "ip_allowlist_empty")

    @property
    def observed_ip(self) -> Optional[str]:
        ip = (self.details or {}).get("ip")
        return ip if isinstance(ip, str) else None


class FeatureDisabledError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class InsufficientFundsError(ApiError):
    @property
    def available(self) -> Optional[int]:
        value = (self.details or {}).get("available")
        return value if isinstance(value, int) else None

    @property
    def requested(self) -> Optional[int]:
        value = (self.details or {}).get("requested")
        return value if isinstance(value, int) else None


class ConflictError(ApiError):
    pass


class IdempotencyConflictError(ConflictError):
    pass


class IdempotencyInProgressError(ConflictError):
    pass


class InvalidStateError(ConflictError):
    pass


class RateLimitError(ApiError):
    @property
    def scope(self) -> Optional[str]:
        scope = (self.details or {}).get("scope")
        return scope if isinstance(scope, str) else None


class ProviderError(ApiError):
    pass


class ProviderUnavailableError(ApiError):
    pass


class ServiceUnavailableError(ApiError):
    pass


class InternalError(ApiError):
    pass


_BY_CODE: dict[str, type[ApiError]] = {
    "validation_error": ValidationError,
    "authentication_error": AuthenticationError,
    "permission_error": PermissionDeniedError,
    "feature_disabled": FeatureDisabledError,
    "not_found": NotFoundError,
    "insufficient_funds": InsufficientFundsError,
    "conflict": ConflictError,
    "idempotency_conflict": IdempotencyConflictError,
    "idempotency_in_progress": IdempotencyInProgressError,
    "invalid_state": InvalidStateError,
    "rate_limited": RateLimitError,
    "provider_error": ProviderError,
    "provider_unavailable": ProviderUnavailableError,
    "service_unavailable": ServiceUnavailableError,
}

_BY_STATUS: dict[int, type[ApiError]] = {
    400: ValidationError,
    401: AuthenticationError,
    402: InsufficientFundsError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}


def map_api_error(status: int, code: str, **kwargs: Any) -> ApiError:
    cls = _BY_CODE.get(code) or _BY_STATUS.get(status) or (InternalError if status >= 500 else ApiError)
    return cls(status, code, **kwargs)
