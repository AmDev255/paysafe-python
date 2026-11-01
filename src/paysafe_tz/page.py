from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Iterator
from typing import Any, Callable, Generic, Optional, TypeVar

from ._response import ApiObject, ApiResponse

T = TypeVar("T", bound=ApiObject)


class Page(Generic[T]):
    """One page of a cursor-paginated list. Iterate it for its items; `auto_paging_iter()` walks every page."""

    def __init__(
        self,
        data: list[T],
        has_more: bool,
        next_cursor: Optional[str],
        last_response: ApiResponse,
        fetch_next: Optional[Callable[[str], Page[T]]] = None,
    ) -> None:
        self.data = data
        self.has_more = has_more
        self.next_cursor = next_cursor
        self.last_response = last_response
        self._fetch_next = fetch_next

    @staticmethod
    def from_body(body: Any, response: ApiResponse, fetch_next: Optional[Callable[[str], Page[T]]]) -> Page[T]:
        items, has_more, cursor = _parse(body, response)
        return Page(items, has_more, cursor, response, fetch_next)  # type: ignore[arg-type]

    def __iter__(self) -> Iterator[T]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def next_page(self) -> Optional[Page[T]]:
        if not self.has_more or self.next_cursor is None or self._fetch_next is None:
            return None
        return self._fetch_next(self.next_cursor)

    def auto_paging_iter(self) -> Iterator[T]:
        page: Optional[Page[T]] = self
        while page is not None:
            yield from page.data
            page = page.next_page()

    def to_dict(self) -> dict[str, Any]:
        return {"object": "list", "data": list(self.data), "has_more": self.has_more, "next_cursor": self.next_cursor}


class AsyncPage(Generic[T]):
    def __init__(
        self,
        data: list[T],
        has_more: bool,
        next_cursor: Optional[str],
        last_response: ApiResponse,
        fetch_next: Optional[Callable[[str], Awaitable[AsyncPage[T]]]] = None,
    ) -> None:
        self.data = data
        self.has_more = has_more
        self.next_cursor = next_cursor
        self.last_response = last_response
        self._fetch_next = fetch_next

    @staticmethod
    def from_body(
        body: Any, response: ApiResponse, fetch_next: Optional[Callable[[str], Awaitable[AsyncPage[T]]]]
    ) -> AsyncPage[T]:
        items, has_more, cursor = _parse(body, response)
        return AsyncPage(items, has_more, cursor, response, fetch_next)  # type: ignore[arg-type]

    def __iter__(self) -> Iterator[T]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    async def next_page(self) -> Optional[AsyncPage[T]]:
        if not self.has_more or self.next_cursor is None or self._fetch_next is None:
            return None
        return await self._fetch_next(self.next_cursor)

    async def auto_paging_iter(self) -> AsyncIterator[T]:
        page: Optional[AsyncPage[T]] = self
        while page is not None:
            for item in page.data:
                yield item
            page = await page.next_page()

    def __aiter__(self) -> AsyncIterator[T]:
        return self.auto_paging_iter()

    def to_dict(self) -> dict[str, Any]:
        return {"object": "list", "data": list(self.data), "has_more": self.has_more, "next_cursor": self.next_cursor}


def _parse(body: Any, response: ApiResponse) -> tuple[list[ApiObject], bool, Optional[str]]:
    body = body if isinstance(body, dict) else {}
    raw_items = body.get("data")
    items = (
        [ApiObject(item, response) for item in raw_items if isinstance(item, dict)]
        if isinstance(raw_items, list)
        else []
    )
    cursor = body.get("next_cursor")
    return items, body.get("has_more") is True, cursor if isinstance(cursor, str) else None
