from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from shuffler.strategies import Strategy

from .protocol import AsyncShuffler, TaskID


@asynccontextmanager
async def move_on_after(timeout: float) -> AsyncIterator[None]:
    with suppress(TimeoutError):
        async with asyncio.timeout(timeout):
            yield


class AsyncioShuffler(AsyncShuffler):
    def __init__(
        self,
        pool_size: int,
        strategy: Strategy[TaskID],
        max_wait_for: float = 0.020,
    ) -> None:
        self._pending: set[TaskID] = set()
        self._strategy = strategy

        self._op_finished = asyncio.Event()
        self._pool_changed = asyncio.Event()
        self._pool_size = pool_size
        self._cur_pool_size = pool_size
        self._max_wait_for = max_wait_for

        self._op_finished.set()

    @asynccontextmanager
    async def shuffle(self, task_id: TaskID) -> AsyncIterator[None]:
        self._pending.add(task_id)
        self._pool_changed.set()

        while True:
            async with move_on_after(self._max_wait_for):
                while True:
                    if (
                        task_id not in self._pending
                        or len(self._pending) >= self._cur_pool_size
                    ):
                        break

                    self._pool_changed.clear()
                    await self._pool_changed.wait()

            if task_id not in self._pending:
                break

            await self._op_finished.wait()
            self._op_finished.clear()
            to_release = self._strategy.choose_next(self._pending)
            self._pending.remove(to_release)
            self._pool_changed.set()

            if task_id not in self._pending:
                break

        try:
            yield
        finally:
            self._op_finished.set()

    def decrement_pool_size(self) -> None:
        self._cur_pool_size -= 1
        assert self._cur_pool_size >= 0
        self._pool_changed.set()

    def finish_sequence(self) -> list[TaskID]:
        self._cur_pool_size = self._pool_size
        return self._strategy.finish_sequence()

    def strategy_completed(self) -> bool:
        return self._strategy.is_completed()

    def reset(self) -> None:
        self._cur_pool_size = self._pool_size
        self._op_finished.set()
        self._strategy.reset()
