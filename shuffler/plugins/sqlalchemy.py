import asyncio
import logging
import time
from contextlib import suppress
from contextvars import ContextVar
from typing import Any, AsyncIterator, Callable, Coroutine, Self, TypeAlias

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.util.concurrency import await_fallback

from shuffler.strategies import ExhaustiveStrategy, Strategy

logger = logging.getLogger(__name__)

TaskID: TypeAlias = int

current_task: ContextVar[TaskID | None] = ContextVar("current_task", default=None)


class AlchemyPlugin:
    def __init__(
        self,
        engine: AsyncEngine,
        strategy: Strategy[TaskID] = ExhaustiveStrategy(),
        max_wait_for: float = 0.020,
    ) -> None:
        self._engine = engine.sync_engine
        self._strategy = strategy
        self._max_wait_for = max_wait_for

        self._pending: set[TaskID] = set()
        self._pool_changed = asyncio.Event()
        self._cur_pool_size = 0
        self._is_started = False

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def start(self) -> None:
        event.listen(
            self._engine,
            "before_cursor_execute",
            self._before_execute,
            named=True,
        )
        self._is_started = True
        logger.debug("`before_cursor_execute` hook installed")

    def stop(self) -> None:
        event.remove(
            self._engine,
            "before_cursor_execute",
            self._before_execute,
        )
        self._is_started = False
        logger.debug("`before_cursor_execute` hook removed")

    def _before_execute(
        self,
        statement: str,
        **_: Any,
    ) -> None:
        if (task_id := current_task.get()) is None:
            return

        self._shuffle(task_id)
        logger.debug("Task %s: Executing query: %s", task_id, statement)

    def _shuffle(self, task_id: TaskID) -> None:
        self._pending.add(task_id)
        self._pool_changed.set()

        while True:
            elapsed = 0.0
            started_at = time.monotonic()
            while elapsed < self._max_wait_for:
                if (
                    task_id not in self._pending
                    or len(self._pending) >= self._cur_pool_size
                ):
                    break

                self._pool_changed.clear()
                with suppress(TimeoutError):
                    await_fallback(
                        asyncio.wait_for(
                            self._pool_changed.wait(),
                            self._max_wait_for - elapsed,
                        )
                    )
                elapsed = time.monotonic() - started_at

            if task_id not in self._pending:
                break

            to_release = self._strategy.choose_next(self._pending)
            self._pending.remove(to_release)
            self._pool_changed.set()

            if task_id not in self._pending:
                break

    def _decrement_pool_size(self) -> None:
        self._cur_pool_size -= 1
        assert self._cur_pool_size >= 0
        self._pool_changed.set()

    def _finish_sequence(self) -> list[TaskID]:
        return self._strategy.finish_sequence()

    def strategy_completed(self) -> bool:
        return self._strategy.is_completed()

    def reset(self) -> None:
        self._strategy.reset()

    async def run(
        self,
        *operations: Callable[[], Coroutine[Any, Any, Any]],
    ) -> AsyncIterator[list[TaskID]]:
        assert len(operations) > 1
        self.reset()

        logger.info("Exploring interleavings for %s operations", len(operations))
        with self:
            counter = 1
            while not self.strategy_completed():
                logger.info("Starting iteration: %s", counter)
                counter += 1
                yield await self.run_single_pass(*operations)

        logger.info("Finished")

    async def run_single_pass(
        self,
        *operations: Callable[[], Coroutine[Any, Any, Any]],
    ) -> list[TaskID]:
        assert not self.strategy_completed()
        assert self._is_started
        assert len(operations) > 1

        self._cur_pool_size = len(operations)

        async def wrapper(
            operation: Callable[[], Coroutine[Any, Any, Any]],
            task_id: int,
        ) -> None:
            token = current_task.set(task_id)
            try:
                await operation()
            finally:
                current_task.reset(token)
                self._decrement_pool_size()

        async with asyncio.TaskGroup() as tg:
            for ix, operation in enumerate(operations, start=1):
                tg.create_task(wrapper(operation, task_id=ix))

        return self._strategy.finish_sequence()
