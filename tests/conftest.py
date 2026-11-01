from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

from paysafe_tz import AsyncPaySafe, PaySafe

FIXTURES = Path(__file__).parent / "fixtures"
TEST_KEY = "paysafe_test_9f2Kx7Qm3Rt8Vw2Yz5Ab1Cd4Ef6Gh9Jk"
REQUEST_ID = "req_01J7A9Q0K3M4N5P6R7S8T9V0W1"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def success_of(fixture: dict[str, Any]) -> tuple[int, Any, dict[str, str]]:
    code = next(c for c in fixture["responses"] if c.startswith("2"))
    response = fixture["responses"][code]
    return int(code), response["body"], response["headers"]


class Queue:
    """Scripted responses for httpx.MockTransport; records every request."""

    def __init__(self) -> None:
        self.items: list[Any] = []
        self.requests: list[httpx.Request] = []

    def json(self, status: int, body: Any, headers: dict[str, str] | None = None) -> Queue:
        h = {"x-request-id": REQUEST_ID}
        h.update({k.lower(): v for k, v in (headers or {}).items()})
        content = b"" if body is None else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
        if content and "content-type" not in h:
            h["content-type"] = "application/json"
        self.items.append(httpx.Response(status, headers=h, content=content))
        return self

    def raw(self, status: int, content: bytes, headers: dict[str, str] | None = None) -> Queue:
        self.items.append(httpx.Response(status, headers=headers or {}, content=content))
        return self

    def error(self, exc: Exception) -> Queue:
        self.items.append(exc)
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.items:
            raise AssertionError(f"No queued response for {request.method} {request.url}")
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[no-any-return]

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_body(self) -> Any:
        return json.loads(self.last.content) if self.last.content else None

    @property
    def pending(self) -> int:
        return len(self.items)


class Sleeps:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    async def async_sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    @property
    def total(self) -> float:
        return sum(self.sleeps)


def make_client(max_retries: int = 4, timeout: float = 30.0) -> tuple[PaySafe, Queue, Sleeps]:
    queue = Queue()
    sleeps = Sleeps()
    client = PaySafe(
        TEST_KEY,
        base_url="https://api.test.invalid",
        max_retries=max_retries,
        timeout=timeout,
        http_client=httpx.Client(transport=httpx.MockTransport(queue.handler)),
        sleep=sleeps,
        rng=lambda: 0.5,
    )
    return client, queue, sleeps


def make_async_client(max_retries: int = 4) -> tuple[AsyncPaySafe, Queue, Sleeps]:
    queue = Queue()
    sleeps = Sleeps()
    client = AsyncPaySafe(
        TEST_KEY,
        base_url="https://api.test.invalid",
        max_retries=max_retries,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(queue.handler)),
        sleep=sleeps.async_sleep,
        rng=lambda: 0.5,
    )
    return client, queue, sleeps


@pytest.fixture
def client_factory() -> Callable[..., tuple[PaySafe, Queue, Sleeps]]:
    return make_client
