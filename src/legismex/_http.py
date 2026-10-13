"""Helpers for complete, bounded asynchronous page retrieval."""

import asyncio
from collections.abc import Iterable
from typing import Optional

import httpx


async def fetch_pages(
    client: httpx.AsyncClient,
    requests: Iterable[tuple[str, Optional[dict]]],
    *,
    concurrency: int = 5,
) -> list[httpx.Response]:
    """Fetch pages in order, raising if any page fails instead of dropping it.

    All workers settle before raising so callers can safely close their client.
    """
    if concurrency < 1:
        raise ValueError("concurrency debe ser al menos 1")
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(url: str, params: Optional[dict]) -> httpx.Response:
        async with semaphore:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response

    results = await asyncio.gather(
        *(fetch(url, params) for url, params in requests), return_exceptions=True
    )
    responses = []
    for result in results:
        if isinstance(result, BaseException):
            raise result
        responses.append(result)
    return responses
