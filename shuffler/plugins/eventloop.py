import asyncio
from collections import deque
from contextlib import contextmanager
from typing import Deque, Iterator, Self

from shuffler.strategies import ExhaustiveStrategy, Strategy


class ShufflingLoop(asyncio.SelectorEventLoop):
    def __init__(self, fake_deque: Deque[asyncio.Handle]) -> None:
        super().__init__()
        self._ready = fake_deque


class EventLoopPlugin:
    def __init__(
        self,
        strategy: Strategy[int] = ExhaustiveStrategy(),
    ) -> None:
        self._strategy = strategy
        self.enabled = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    @contextmanager
    def activate(self) -> Iterator[Self]:
        self.enable()
        try:
            yield self
        finally:
            self.disable()

    def new_event_loop(self) -> ShufflingLoop:
        return _new_event_loop(self)

    def event_loop_policy(self) -> asyncio.AbstractEventLoopPolicy:
        return _event_loop_policy(self)

    def strategy_completed(self) -> bool:
        return self._strategy.is_completed()

    def finish_sequence(self) -> list[int]:
        return self._strategy.finish_sequence()

    def reset(self) -> None:
        self._strategy.reset()


def _event_loop_policy(plugin: EventLoopPlugin) -> asyncio.AbstractEventLoopPolicy:
    class ShufflingLoopPolicy(asyncio.DefaultEventLoopPolicy):
        def new_event_loop(self) -> ShufflingLoop:
            return plugin.new_event_loop()

    return ShufflingLoopPolicy()


def _new_event_loop(plugin: EventLoopPlugin) -> ShufflingLoop:
    class FakeDeque(deque[asyncio.Handle]):
        def popleft(self) -> asyncio.Handle:
            if plugin.enabled and len(self) > 1:
                ix = plugin._strategy.choose_next(set(range(len(self))))
                nxt = self[ix]
                self.remove(self[ix])
                return nxt

            return super().popleft()

    return ShufflingLoop(FakeDeque())
