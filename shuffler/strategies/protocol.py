from typing import Any, Hashable, Protocol, TypeVar


class HashableComparable(Hashable, Protocol):
    def __lt__(self, other: Any, /) -> bool: ...


T = TypeVar("T", bound=HashableComparable)


class Strategy(Protocol[T]):
    def choose_next(self, options: set[T]) -> T: ...

    def finish_sequence(self) -> list[T]: ...

    def is_completed(self) -> bool: ...

    def reset(self) -> None: ...
