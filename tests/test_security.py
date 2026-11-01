from __future__ import annotations

import httpx
import pytest

from paysafe_tz import (
    ApiConnectionError,
    ApiError,
    ConfigurationError,
    InvalidRequestError,
    PaySafe,
    RequestOptions,
    verify_signature,
)

from .conftest import TEST_KEY, Queue, load, make_client, success_of

_, PAYMENT, _ = success_of(load("getPayment"))
_, LIST, _ = success_of(load("listPayments"))
VECTOR = load("webhook-vector")


@pytest.mark.parametrize(
    "bad", ["../balance", "pay_1/cancel", "pay_1?limit=1", "pay_1#x", "pay%2F1", "pay 1", "pay_1\n", "", "a" * 65]
)
def test_ids_that_could_change_the_path_are_rejected(bad: str) -> None:
    client, queue, _ = make_client()
    with pytest.raises(InvalidRequestError):
        client.payments.get(bad)
    assert queue.requests == []


def test_ids_and_query_values_are_encoded() -> None:
    client, queue, _ = make_client()
    queue.json(200, PAYMENT)
    client.payments.get("pay_01J7A9Q0K3M4N5P6R7S8T9V0W1")
    assert str(queue.last.url) == "https://api.test.invalid/v1/payments/pay_01J7A9Q0K3M4N5P6R7S8T9V0W1"
    queue.json(200, LIST)
    client.payments.list({"reference": "order&x=1 #2", "limit": 5})
    assert str(queue.last.url) == "https://api.test.invalid/v1/payments?reference=order%26x%3D1%20%232&limit=5"


@pytest.mark.parametrize("value", ["abc\r\nX-Injected: 1", "abc\nX-Injected: 1", "abc\0"])
def test_header_injection_is_rejected(value: str) -> None:
    with pytest.raises(InvalidRequestError):
        RequestOptions(headers={"X-Custom": value})


def test_bad_keys_request_ids_and_protected_headers() -> None:
    with pytest.raises(InvalidRequestError):
        RequestOptions(idempotency_key="key\r\nX: 1")
    with pytest.raises(InvalidRequestError):
        RequestOptions(request_id="bad id")
    with pytest.raises(InvalidRequestError):
        RequestOptions(headers={"authorization": "Bearer other"})


@pytest.mark.parametrize(
    "url",
    [
        "http://api.paysafe.co.tz",
        "https://user:pass@api.paysafe.co.tz",
        "https://api.paysafe.co.tz/?x=1",
        "https://api.paysafe.co.tz/#x",
        "api.paysafe.co.tz",
        "https://api.paysafe.co.tz\n",
        "ftp://api.paysafe.co.tz",
    ],
)
def test_unsafe_base_urls_are_rejected(url: str) -> None:
    with pytest.raises(ConfigurationError):
        PaySafe(TEST_KEY, base_url=url, http_client=httpx.Client(transport=httpx.MockTransport(Queue().handler)))


def test_plain_http_only_for_loopback_or_opt_in() -> None:
    http = httpx.Client(transport=httpx.MockTransport(Queue().handler))
    assert PaySafe(TEST_KEY, base_url="http://localhost:8088", http_client=http).environment == "test"
    assert (
        PaySafe(TEST_KEY, base_url="http://api.internal", allow_insecure_http=True, http_client=http).environment
        == "test"
    )
    with pytest.raises(ConfigurationError):
        PaySafe(TEST_KEY + "\n", http_client=http)


def test_redirects_are_never_followed() -> None:
    client, queue, _ = make_client()
    queue.raw(302, b"", {"location": "https://evil.invalid/steal"})
    with pytest.raises(ApiError) as info:
        client.balance.get()
    assert info.value.code == "unexpected_redirect"
    assert len(queue.requests) == 1


def test_oversized_bodies_and_metadata_are_rejected_before_sending() -> None:
    client, queue, _ = make_client()
    base = {"amount": 10000, "customer": {"phone": "+255712340000"}}
    with pytest.raises(InvalidRequestError):
        client.payments.create({**base, "metadata": {"big": "b" * 70000}})
    with pytest.raises(InvalidRequestError):
        client.payments.create({**base, "metadata": {"x": "y" * 9000}})
    assert queue.requests == []


def test_amounts_phones_and_enums_are_validated() -> None:
    client, _, _ = make_client()
    for bad in ["10000", 10000.5, True, None]:
        with pytest.raises(InvalidRequestError) as info:
            client.payments.create({"amount": bad, "customer": {"phone": "+255712340000"}})
        assert info.value.param == "amount"
    for phone in ["0712340000", "+25571234000", "+255 712 340 000", "+1255712340000", "+255712340000\n"]:
        with pytest.raises(InvalidRequestError) as info:
            client.payments.create({"amount": 10000, "customer": {"phone": phone}})
        assert info.value.param == "customer.phone"
    with pytest.raises(InvalidRequestError):
        client.payments.create({"amount": 10000, "customer": {"phone": "+255712340000"}, "channel": "paypal"})
    with pytest.raises(InvalidRequestError):
        client.webhook_endpoints.create({"url": "http://merchant.example/hook"})
    with pytest.raises(InvalidRequestError):
        client.payments.list({"cursor": "c" * 201})


def test_oversized_responses_are_refused_without_retry() -> None:
    client, queue, _ = make_client()
    queue.raw(200, b"x", {"content-length": str(16 * 1024 * 1024 + 1)})
    with pytest.raises(ApiConnectionError):
        client.balance.get()
    assert len(queue.requests) == 1


def test_non_json_error_bodies_are_truncated_and_key_never_leaks() -> None:
    client, queue, _ = make_client(max_retries=0)
    queue.raw(400, b"<b>" * 5000, {"content-type": "text/html"})
    with pytest.raises(ApiError) as info:
        client.balance.get()
    assert info.value.code == "unknown"
    assert info.value.details is not None and len(info.value.details["raw"]) <= 4096
    assert TEST_KEY not in str(info.value)
    assert TEST_KEY not in repr(info.value.headers)


def test_webhook_input_sizes_are_bounded() -> None:
    assert verify_signature(VECTOR["secret"], "x" * 1048577, VECTOR["header"], now=VECTOR["nowValid"]) is False
    assert verify_signature(VECTOR["secret"], VECTOR["body"], "t" * 5000, now=VECTOR["nowValid"]) is False
