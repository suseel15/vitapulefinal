import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def bounded_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    retryable: Callable[[Exception], bool],
    base_delay_seconds: float = 0.25,
) -> T:
    for attempt in range(attempts):
        try:
            return await operation()
        except Exception as error:
            if attempt + 1 >= attempts or not retryable(error):
                raise
            delay = min(4.0, base_delay_seconds * (2**attempt))
            await asyncio.sleep(delay + random.uniform(0, delay / 4))
    raise RuntimeError("Retry loop exited without a result.")
