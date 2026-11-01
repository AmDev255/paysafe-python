from __future__ import annotations

import pytest

from paysafe_tz import ApiError, AsyncPage, PollingTimeoutError

from .conftest import load, make_async_client, success_of

_, BALANCE, _ = success_of(load("getBalance"))
_, PAYMENT, _ = success_of(load("getPayment"))
CODE, CREATED, HEADERS = success_of(load("createPayment"))


async def test_async_balance_and_metadata() -> None:
    client, queue, _ = make_async_client()
    queue.json(200, BALANCE, {"x-ratelimit-remaining": "49"})
    async with client:
        balance = await client.balance.get()
    assert balance.livemode is False
    assert balance.last_response is not None and balance.last_response.rate_limit.remaining == 49  # type: ignore[union-attr]


async def test_async_create_retries_with_same_key() -> None:
    client, queue, sleeps = make_async_client()
    queue.json(500, {"error": {"code": "internal_error", "message": "x", "request_id": "r"}})
    queue.json(CODE, CREATED, HEADERS)
    payment = await client.payments.create({"amount": 10000, "customer": {"phone": "+255712340000"}})
    assert payment.id == CREATED["id"]
    assert queue.requests[0].headers["idempotency-key"] == queue.requests[1].headers["idempotency-key"]
    assert len(sleeps.sleeps) == 1


async def test_async_paging_and_polling() -> None:
    client, queue, sleeps = make_async_client()
    queue.json(200, {"object": "list", "data": [{**PAYMENT, "id": "pay_1"}], "has_more": True, "next_cursor": "c2"})
    queue.json(200, {"object": "list", "data": [{**PAYMENT, "id": "pay_2"}], "has_more": False, "next_cursor": None})
    page = await client.payments.list({"limit": 1})
    assert isinstance(page, AsyncPage)
    assert [p.id async for p in page] == ["pay_1", "pay_2"]

    for status in ["pending", "succeeded"]:
        queue.json(200, {**PAYMENT, "status": status})
    final = await client.payments.wait_for_terminal("pay_01J7A9Q0K3M4N5P6R7S8T9V0W1")
    assert final.status == "succeeded" and sleeps.sleeps[-1] == 2.0

    queue.json(200, {**PAYMENT, "status": "processing"})
    with pytest.raises(PollingTimeoutError):
        await client.payments.wait_for_terminal("pay_01J7A9Q0K3M4N5P6R7S8T9V0W1", timeout=0, should_stop=lambda: True)


async def test_async_errors_map() -> None:
    client, queue, _ = make_async_client(max_retries=0)
    queue.json(404, {"error": {"code": "not_found", "message": "x", "request_id": "r"}})
    with pytest.raises(ApiError) as info:
        await client.payments.get("pay_missing")
    assert info.value.status == 404
