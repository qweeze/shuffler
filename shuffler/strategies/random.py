from random import Random

from .protocol import Strategy, T


class RandomStrategy(Strategy[T]):
    def __init__(self, max_iterations: int = 100) -> None:
        self.max_iterations = max_iterations

        self._rand = Random()
        self._counter = 0
        self._curr_path: list[T] = []

    def seed(self, state: float | str | bytes) -> None:
        self._rand.seed(state)

    def choose_next(self, options: set[T]) -> T:
        assert options
        selected = self._rand.choice(list(options))
        self._curr_path.append(selected)
        return selected

    def finish_sequence(self) -> list[T]:
        self._counter += 1
        path, self._curr_path = self._curr_path, []
        return path

    def is_completed(self) -> bool:
        return self._counter >= self.max_iterations

    def reset(self) -> None:
        self._counter = 0
        self._curr_path = []
