from __future__ import annotations

import pytest

from paysafe_tz import PollingTimeoutError

from .conftest import load, make_client, success_of

_, PAYMENT, _ = success_of(load("getPayment"))
_, REFUND, _ = success_of(load("getRefund"))
_, TRANSFER, _ = success_of(load("getTransfer"))


def test_auto_paging_keeps_filters() -> None:
    client, queue, _ = make_client()
    queue.json(
        200,
        {
            "object": "list",
            "data": [{**PAYMENT, "id": "pay_1"}, {**PAYMENT, "id": "pay_2"}],
            "has_more": True,
            "next_cursor": "c2",
        },
    )
    queue.json(200, {"object": "list", "data": [{**PAYMENT, "id": "pay_3"}], "has_more": False, "next_cursor": None})
    page = client.payments.list({"status": "succeeded", "limit": 2})
    assert len(page) == 2 and page.has_more
    assert [p.id for p in page.auto_paging_iter()] == ["pay_1", "pay_2", "pay_3"]
    assert len(queue.requests) == 2
    assert str(queue.requests[1].url) == "https://api.test.invalid/v1/payments?status=succeeded&limit=2&cursor=c2"
    assert [p["id"] for p in page] == ["pay_1", "pay_2"]


def test_last_page_has_no_next() -> None:
    client, queue, _ = make_client()
    queue.json(200, {"object": "list", "data": [], "has_more": False, "next_cursor": None})
    page = client.customers.list()
    assert page.next_page() is None
    assert page.to_dict() == {"object": "list", "data": [], "has_more": False, "next_cursor": None}


def test_wait_for_terminal_reports_updates() -> None:
    client, queue, sleeps = make_client()
    for status in ["pending", "processing", "processing", "succeeded"]:
        queue.json(200, {**PAYMENT, "status": status})
    seen: list[str] = []
    final = client.payments.wait_for_terminal(
        "pay_01J7A9Q0K3M4N5P6R7S8T9V0W1", on_update=lambda p: seen.append(p.status)
    )
    assert final.status == "succeeded"
    assert seen == ["pending", "processing", "succeeded"]
    assert sleeps.sleeps == [2.0, 2.0, 2.0]


def test_wait_times_out_with_last_object() -> None:
    client, queue, _ = make_client()
    for _ in range(4):
        queue.json(200, {**PAYMENT, "status": "processing"})
    with pytest.raises(PollingTimeoutError) as info:
        client.payments.wait_for_terminal("pay_01J7A9Q0K3M4N5P6R7S8T9V0W1", interval=2.0, timeout=6.0)
    assert info.value.last_seen["status"] == "processing"
    assert len(queue.requests) == 4


def test_wait_can_be_cancelled() -> None:
    client, queue, _ = make_client()
    queue.json(200, {**REFUND, "status": "pending"})
    with pytest.raises(PollingTimeoutError):
        client.refunds.wait_for_terminal("rfd_01J7A9Q0K3M4N5P6R7S8T9V0W1", should_stop=lambda: True)


def test_wait_slows_down_after_thirty_seconds() -> None:
    client, queue, sleeps = make_client()
    for _ in range(20):
        queue.json(200, {**TRANSFER, "status": "in_review"})
    queue.json(200, {**TRANSFER, "status": "completed"})
    client.transfers.wait_for_terminal("trf_01J7A9Q0K3M4N5P6R7S8T9V0W1")
    assert sleeps.sleeps[0] == 2.0 and sleeps.sleeps[-1] == 5.0
