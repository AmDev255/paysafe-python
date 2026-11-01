from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import parse_qs

import pytest

from paysafe_tz import ApiError, ApiObject, Page, PaySafe, RequestOptions

from .conftest import REQUEST_ID, TEST_KEY, load, make_client, success_of

ID = "pay_01J7A9Q0K3M4N5P6R7S8T9V0W1"
KEY = "order-8812-attempt-1"
OPTS = RequestOptions(idempotency_key=KEY)

CALLS: dict[str, Callable[[PaySafe, dict[str, Any]], Any]] = {
    "createPayment": lambda c, f: c.payments.create(f["body"], OPTS),
    "listPayments": lambda c, f: c.payments.list(f["query"]),
    "getPayment": lambda c, f: c.payments.get(ID),
    "cancelPayment": lambda c, f: c.payments.cancel(ID, f["body"], OPTS),
    "createPaymentLink": lambda c, f: c.payment_links.create(f["body"]),
    "listPaymentLinks": lambda c, f: c.payment_links.list(f["query"]),
    "getPaymentLink": lambda c, f: c.payment_links.get(ID),
    "updatePaymentLink": lambda c, f: c.payment_links.update(ID, f["body"]),
    "createControlNumber": lambda c, f: c.control_numbers.create(f["body"]),
    "listControlNumbers": lambda c, f: c.control_numbers.list(f["query"]),
    "getControlNumber": lambda c, f: c.control_numbers.get(ID),
    "cancelControlNumber": lambda c, f: c.control_numbers.cancel(ID, f["body"]["reason"]),
    "createRefund": lambda c, f: c.refunds.create(f["body"], OPTS),
    "listRefunds": lambda c, f: c.refunds.list(f["query"]),
    "getRefund": lambda c, f: c.refunds.get(ID),
    "getBalance": lambda c, f: c.balance.get(),
    "listTransactions": lambda c, f: c.balance.transactions(f["query"]),
    "listCustomers": lambda c, f: c.customers.list(f["query"]),
    "getCustomer": lambda c, f: c.customers.get(ID),
    "createTransfer": lambda c, f: c.transfers.create(f["body"], OPTS),
    "listTransfers": lambda c, f: c.transfers.list(f["query"]),
    "getTransfer": lambda c, f: c.transfers.get(ID),
    "listWebhookEndpoints": lambda c, f: c.webhook_endpoints.list(),
    "createWebhookEndpoint": lambda c, f: c.webhook_endpoints.create(f["body"]),
    "getWebhookEndpoint": lambda c, f: c.webhook_endpoints.get(ID),
    "updateWebhookEndpoint": lambda c, f: c.webhook_endpoints.update(ID, f["body"]),
    "deleteWebhookEndpoint": lambda c, f: c.webhook_endpoints.delete(ID),
    "listEvents": lambda c, f: c.events.list(f["query"]),
    "getEvent": lambda c, f: c.events.get(ID),
}

OPERATIONS = [op["operationId"] for op in load("index")["operations"]]


def test_every_operation_has_a_call() -> None:
    assert sorted(CALLS) == sorted(OPERATIONS)


@pytest.mark.parametrize("operation_id", OPERATIONS)
def test_request_matches_fixture_and_success_parses(operation_id: str) -> None:
    fixture = load(operation_id)
    code, body, headers = success_of(fixture)
    client, queue, _ = make_client()
    queue.json(code, body, headers)
    result = CALLS[operation_id](client, fixture)
    request = queue.last

    assert request.method == fixture["method"]
    assert request.url.path == fixture["resolvedPath"]
    expected_query = {
        k: [str(v).lower() if isinstance(v, bool) else str(v)] for k, v in fixture["query"].items() if v is not None
    }
    assert parse_qs(request.url.query.decode(), keep_blank_values=True) == expected_query
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    if "Idempotency-Key" in fixture["headers"]:
        assert request.headers["idempotency-key"] == KEY
    else:
        assert "idempotency-key" not in request.headers
    if fixture["body"] is not None:
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.content) == fixture["body"]
    else:
        assert request.content == b""

    if body is None:
        assert result is None
    elif body.get("object") == "list" and operation_id != "listWebhookEndpoints":
        assert isinstance(result, Page)
        assert len(result) == len(body["data"])
        assert result.has_more == body["has_more"] and result.next_cursor == body["next_cursor"]
        for item in result:
            assert isinstance(item, ApiObject) and item.get("id")
    elif operation_id == "listWebhookEndpoints":
        assert isinstance(result, list) and len(result) == len(body["data"])
        assert [dict(i) for i in result] == body["data"]
    else:
        assert isinstance(result, ApiObject)
        assert dict(result) == body
        assert result.request_id == REQUEST_ID


@pytest.mark.parametrize("operation_id", OPERATIONS)
def test_every_documented_error_raises_the_mapped_exception(operation_id: str) -> None:
    fixture = load(operation_id)
    for code, response in fixture["responses"].items():
        if code.startswith("2"):
            continue
        client, queue, _ = make_client(max_retries=0)
        status = int(code.split("_")[0])
        queue.json(status, response["body"], response["headers"])
        with pytest.raises(ApiError) as info:
            CALLS[operation_id](client, fixture)
        assert info.value.status == status, f"{operation_id} {code}"
        assert info.value.code == response["code"]
        assert info.value.request_id == response["body"]["error"]["request_id"]
        assert info.value.doc_url == response["body"]["error"].get("doc_url")
        if "Retry-After" in response["headers"]:
            assert info.value.retry_after == int(response["headers"]["Retry-After"])
