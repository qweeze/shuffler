from typing import (
    AsyncContextManager,
    ContextManager,
    Protocol,
    TypeAlias,
)

from shuffler.strategies import Strategy

TaskID: TypeAlias = str


class SyncShuffler(Protocol):
    def __init__(
        self,
        pool_size: int,
        strategy: Strategy[TaskID],
        max_wait_for: float,
    ) -> None: ...

    def shuffle(self, task_id: TaskID) -> ContextManager[None]: ...

    def finish_sequence(self) -> list[TaskID]: ...

    def strategy_completed(self) -> bool: ...


class AsyncShuffler(Protocol):
    def __init__(
        self,
        pool_size: int,
        strategy: Strategy[TaskID],
        max_wait_for: float,
    ) -> None: ...

    def shuffle(self, task_id: TaskID) -> AsyncContextManager[None]: ...

    def finish_sequence(self) -> list[TaskID]: ...

    def strategy_completed(self) -> bool: ...
