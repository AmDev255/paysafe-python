from __future__ import annotations

from typing import Any

import httpx
import pytest

from paysafe_tz import (
    ApiConnectionError,
    ApiError,
    ApiTimeoutError,
    IdempotencyConflictError,
    InternalError,
    PaySafe,
    PaySafeError,
    ProviderError,
    RequestOptions,
    ValidationError,
)

from .conftest import load, make_client, success_of

ERRORS: dict[str, type[PaySafeError]] = {
    "ApiError": ApiError,
    "ApiConnectionError": ApiConnectionError,
    "IdempotencyConflictError": IdempotencyConflictError,
    "ValidationError": ValidationError,
    "InternalError": InternalError,
    "ProviderError": ProviderError,
}

SCENARIOS = load("retry-scenarios")["scenarios"]


def call(client: PaySafe, operation_id: str, fixture: dict[str, Any]) -> Any:
    if operation_id == "getBalance":
        return client.balance.get()
    if operation_id == "getPayment":
        return client.payments.get("pay_01J7A9Q0K3M4N5P6R7S8T9V0W1")
    if operation_id == "listPayments":
        return client.payments.list()
    if operation_id == "createPayment":
        return client.payments.create(fixture["minimalBody"])
    if operation_id == "createRefund":
        return client.refunds.create(fixture["minimalBody"])
    if operation_id == "createWebhookEndpoint":
        return client.webhook_endpoints.create(fixture["minimalBody"])
    raise AssertionError(f"unsupported operation {operation_id}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_scenario(scenario: dict[str, Any]) -> None:
    fixture = load(scenario["request"])
    _code, body, headers = success_of(fixture)
    client, queue, sleeps = make_client()
    for step in scenario["sequence"]:
        if step.get("networkError"):
            queue.error(httpx.ConnectError("Connection refused"))
        elif step.get("timeout"):
            queue.error(httpx.ReadTimeout("timed out"))
        elif "rawBody" in step:
            queue.raw(step["status"], step["rawBody"].encode(), {"content-type": "text/html"})
        elif step["status"] < 300:
            queue.json(step["status"], body, {**headers, **step.get("headers", {})})
        else:
            error_code = step.get("code", "internal_error")
            queue.json(
                step["status"],
                {"error": {"code": error_code, "message": error_code, "request_id": "req_x"}},
                step.get("headers"),
            )

    expect = scenario["expect"]
    result = None
    raised: PaySafeError | None = None
    try:
        result = call(client, scenario["request"], fixture)
    except PaySafeError as exc:
        raised = exc

    if "error" in expect:
        assert isinstance(raised, ERRORS[expect["error"]]), f"expected {expect['error']}, got {raised!r}"
        if "code" in expect:
            assert isinstance(raised, ApiError) and raised.code == expect["code"]
    else:
        assert raised is None, repr(raised)
    assert len(queue.requests) == expect["attempts"], "attempt count"
    assert queue.pending == 0, "every queued response consumed"
    if expect.get("sameIdempotencyKey"):
        keys = {r.headers.get("idempotency-key") for r in queue.requests}
        assert len(keys) == 1 and None not in keys
    if "sleptAtLeastMs" in expect:
        assert sleeps.total * 1000 >= expect["sleptAtLeastMs"]
    if "idempotentReplayed" in expect:
        assert result is not None and result.last_response.idempotent_replayed is expect["idempotentReplayed"]


def test_timeout_is_distinguished() -> None:
    client, queue, _ = make_client(max_retries=0)
    queue.error(httpx.ReadTimeout("timed out"))
    with pytest.raises(ApiTimeoutError):
        client.balance.get()


def test_per_request_max_retries_and_generated_key_reuse() -> None:
    client, queue, _ = make_client()
    queue.json(503, {"error": {"code": "service_unavailable", "message": "x", "request_id": "r"}})
    with pytest.raises(ApiError):
        client.payments.create(
            {"amount": 10000, "customer": {"phone": "+255712340000"}},
            RequestOptions(idempotency_key="k-1", max_retries=0),
        )
    assert len(queue.requests) == 1

    code, body, headers = success_of(load("createPayment"))
    queue.json(500, {"error": {"code": "internal_error", "message": "x", "request_id": "r"}})
    queue.json(code, body, headers)
    payment = client.payments.create({"amount": 10000, "customer": {"phone": "+255712340000"}})
    key = payment.last_response.idempotency_key
    assert key is not None and len(key) == 36
    assert queue.requests[1].headers["idempotency-key"] == key
    assert queue.requests[2].headers["idempotency-key"] == key
