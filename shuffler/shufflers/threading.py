from __future__ import annotations
import threading
import time
from contextlib import contextmanager
from typing import Iterator

from shuffler.strategies import Strategy

from .protocol import SyncShuffler, TaskID


class ThreadingShuffler(SyncShuffler):
    def __init__(
        self,
        pool_size: int,
        strategy: Strategy[TaskID],
        max_wait_for: float = 0.020,
    ) -> None:
        self._pending: set[TaskID] = set()
        self._strategy = strategy

        self._op_finished = threading.Event()
        self._pool_changed = threading.Event()
        self._pool_size = pool_size
        self._cur_pool_size = pool_size
        self._max_wait_for = max_wait_for

        self._op_finished.set()

    @contextmanager
    def shuffle(self, task_id: TaskID) -> Iterator[None]:
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
                self._pool_changed.wait(timeout=self._max_wait_for - elapsed)
                elapsed = time.monotonic() - started_at

            if task_id not in self._pending:
                break

            self._op_finished.wait()
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
