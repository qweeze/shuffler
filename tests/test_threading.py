from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeAlias

import pytest

from shuffler.shufflers.threading import ThreadingShuffler
from shuffler.strategies.exhaustive import ExhaustiveStrategy
from shuffler.util import all_interleavings

Task: TypeAlias = Callable[[], None]


def generate_tasks(
    shuffler: ThreadingShuffler,
    ops_counts: list[int],
) -> tuple[list[Task], list[tuple[int, int]]]:
    output = []

    def make_task(task_ix: int, n_ops: int) -> Task:
        def task() -> None:
            for ix in range(n_ops):
                with shuffler.shuffle(f"Task-{task_ix}"):
                    output.append((task_ix, ix))

            shuffler.decrement_pool_size()

        return task

    tasks = [make_task(task_ix, n_ops) for task_ix, n_ops in enumerate(ops_counts)]

    return tasks, output


@pytest.mark.parametrize(
    "ops_counts",
    (
        [1],
        [1, 1],
        [1, 2],
        [2, 2],
        [3, 2],
        [3, 3],
        [2, 2, 2],
        [1, 2, 3],
    ),
)
def test_exhaustive(ops_counts: list[int]) -> None:
    expected_interleavings = all_interleavings(
        *(
            [(task_ix, op) for op in range(n_ops)]
            for task_ix, n_ops in enumerate(ops_counts)
        )
    )
    expected_sequences = all_interleavings(
        *(
            [f"Task-{task_ix}" for _ in range(n_ops)]
            for task_ix, n_ops in enumerate(ops_counts)
        )
    )
    shuffler = ThreadingShuffler(
        pool_size=len(ops_counts), strategy=ExhaustiveStrategy()
    )
    tasks, output = generate_tasks(shuffler, ops_counts)

    interleavings = []
    sequences = []
    while not shuffler.strategy_completed():
        with ThreadPoolExecutor(max_workers=len(ops_counts)) as pool:
            for task in tasks:
                pool.submit(task)

        interleavings.append(list(output))
        sequence = shuffler.finish_sequence()
        sequences.append(sequence)
        assert len(sequence) == len(output) == len(set(output)) == sum(ops_counts)
        output.clear()

    assert sorted(interleavings) == sorted(expected_interleavings)
    assert sorted(sequences) == sorted(expected_sequences)
