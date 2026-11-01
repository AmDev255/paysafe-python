"""Runs against the real sandbox when PAYSAFE_SECRET_KEY holds a paysafe_test_ key. Never uses a live key."""

from __future__ import annotations

import os
import secrets

import pytest

from paysafe_tz import InvalidStateError, NotFoundError, PaySafe, RequestOptions, ValidationError

KEY = os.environ.get("PAYSAFE_SECRET_KEY", "")
pytestmark = pytest.mark.skipif(not KEY.startswith("paysafe_test_"), reason="PAYSAFE_SECRET_KEY (test key) not set")


@pytest.fixture(scope="module")
def client() -> PaySafe:
    c = PaySafe()
    assert c.environment == "test"
    return c


def test_balance_and_transactions(client: PaySafe) -> None:
    balance = client.balance.get()
    assert balance.livemode is False
    assert balance.request_id
    assert len(client.balance.transactions({"limit": 5})) <= 5


def test_payment_lifecycle(client: PaySafe) -> None:
    payment = client.payments.create(
        {"amount": 10000, "customer": {"phone": "+255712340000"}, "reference": f"sdk-py-{secrets.token_hex(4)}"}
    )
    assert payment.last_response is not None and payment.last_response.status == 202
    final = client.payments.wait_for_terminal(payment.id, timeout=60)
    assert final.status == "succeeded"

    declined = client.payments.create({"amount": 10000, "customer": {"phone": "+255712341111"}})
    failed = client.payments.wait_for_terminal(declined.id, timeout=60)
    assert failed.status == "failed" and failed["failure"]["code"] == "customer_declined"

    assert len(client.payments.list({"limit": 3})) > 0
    assert client.payments.get(payment.id).id == payment.id
    with pytest.raises(InvalidStateError):
        client.payments.cancel(payment.id)


def test_validation_and_not_found(client: PaySafe) -> None:
    with pytest.raises(ValidationError):
        client.request(
            "POST",
            "/v1/payments",
            None,
            {"amount": 5},
            RequestOptions(idempotency_key=f"sdk-py-bad-{secrets.token_hex(4)}"),
        )
    with pytest.raises(NotFoundError):
        client.payments.get("pay_00000000000000000000000000")


def test_webhook_endpoint_round_trip(client: PaySafe) -> None:
    created = client.webhook_endpoints.create(
        {"url": f"https://example.com/paysafe/{secrets.token_hex(4)}", "events": ["payment.succeeded"]}
    )
    assert created.secret.startswith("paysafe_webhook_")
    assert client.webhook_endpoints.update(created.id, {"status": "DISABLED"}).status == "DISABLED"
    assert created.id in [e.id for e in client.webhook_endpoints.list()]
    client.webhook_endpoints.delete(created.id)
    with pytest.raises(NotFoundError):
        client.webhook_endpoints.get(created.id)


def test_events_and_customers(client: PaySafe) -> None:
    for event in client.events.list({"limit": 2}):
        assert client.events.get(event.id).id == event.id
    for customer in client.customers.list({"limit": 2}):
        assert client.customers.get(customer.id).id == customer.id
