from __future__ import annotations

import json

import httpx
import pytest

from paysafe_tz import VERSION, ConfigurationError, PaySafe

from .conftest import REQUEST_ID, TEST_KEY, Queue, load, make_client, success_of

_, BALANCE, _ = success_of(load("getBalance"))


def test_environment_from_key_prefix() -> None:
    http = httpx.Client(transport=httpx.MockTransport(Queue().handler))
    assert PaySafe(TEST_KEY, http_client=http).environment == "test"
    assert PaySafe("paysafe_live_9f2Kx7Qm3Rt8Vw2Yz5Ab1Cd4Ef6Gh9Jk", http_client=http).environment == "live"
    with pytest.raises(ConfigurationError):
        PaySafe("sk_test_abc", http_client=http)


def test_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYSAFE_SECRET_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        PaySafe()


def test_env_key_and_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYSAFE_SECRET_KEY", TEST_KEY)
    monkeypatch.setenv("PAYSAFE_BASE_URL", "http://127.0.0.1:8088/v1")
    queue = Queue().json(200, BALANCE)
    client = PaySafe(http_client=httpx.Client(transport=httpx.MockTransport(queue.handler)))
    client.balance.get()
    assert str(queue.last.url) == "http://127.0.0.1:8088/v1/balance"


def test_standard_headers() -> None:
    client, queue, _ = make_client()
    queue.json(200, BALANCE)
    client.balance.get()
    request = queue.last
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert request.headers["accept"] == "application/json"
    assert request.headers["user-agent"].startswith(f"paysafe-python/{VERSION}")
    assert "content-type" not in request.headers


def test_api_version_header() -> None:
    queue = Queue().json(200, BALANCE)
    client = PaySafe(
        TEST_KEY, api_version="2026-09-07", http_client=httpx.Client(transport=httpx.MockTransport(queue.handler))
    )
    client.balance.get()
    assert queue.last.headers["paysafe-version"] == "2026-09-07"


def test_response_metadata_on_objects() -> None:
    client, queue, _ = make_client()
    queue.json(
        200, BALANCE, {"x-ratelimit-limit": "50", "x-ratelimit-remaining": "49", "x-ratelimit-reset": "1788775205"}
    )
    balance = client.balance.get()
    assert balance.last_response is not None
    assert balance.last_response.status == 200
    assert balance.request_id == REQUEST_ID
    assert balance.last_response.rate_limit is not None
    assert balance.last_response.rate_limit.remaining == 49
    assert balance.last_response.idempotent_replayed is False
    assert json.loads(json.dumps(balance)) == BALANCE
    assert balance.livemode is False
    assert balance["object"] == "balance"


def test_low_level_request() -> None:
    client, queue, _ = make_client()
    queue.json(200, BALANCE)
    response = client.request("get", "v1/balance")
    assert response.status == 200
    assert str(queue.last.url) == "https://api.test.invalid/v1/balance"


def test_logger_records_without_secrets() -> None:
    records: list[dict[str, object]] = []
    queue = Queue().json(200, BALANCE)
    client = PaySafe(
        TEST_KEY, http_client=httpx.Client(transport=httpx.MockTransport(queue.handler)), logger=records.append
    )
    client.balance.get()
    assert len(records) == 1
    assert records[0]["method"] == "GET" and records[0]["path"] == "/v1/balance" and records[0]["status"] == 200
    assert TEST_KEY not in json.dumps(records)


def test_context_manager_closes_owned_client() -> None:
    with PaySafe(TEST_KEY) as client:
        assert client.environment == "test"
