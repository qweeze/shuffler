import asyncio
import random
from typing import Awaitable, Callable, TypeAlias

import pytest

from shuffler.shufflers.asyncio import AsyncioShuffler
from shuffler.strategies.exhaustive import ExhaustiveStrategy
from shuffler.strategies.random import RandomStrategy
from shuffler.util import all_interleavings

Task: TypeAlias = Callable[[], Awaitable[None]]


def generate_tasks(
    shuffler: AsyncioShuffler,
    ops_counts: list[int],
) -> tuple[list[Task], list[tuple[int, int]]]:
    output = []

    def make_task(task_ix: int, n_ops: int) -> Task:
        async def task() -> None:
            for ix in range(n_ops):
                async with shuffler.shuffle(f"Task-{task_ix}"):
                    output.append((task_ix, ix))

            shuffler.decrement_pool_size()

        return task

    tasks = [make_task(task_ix, n_ops) for task_ix, n_ops in enumerate(ops_counts)]

    return tasks, output


async def test_simple() -> None:
    shuffler = AsyncioShuffler(pool_size=2, strategy=ExhaustiveStrategy())

    async def task(task_id: str) -> None:
        async with shuffler.shuffle(f"{task_id}-1"):
            pass
        async with shuffler.shuffle(f"{task_id}-2"):
            pass

    sequences = []
    while not shuffler.strategy_completed():
        await asyncio.gather(task("A"), task("B"))
        sequence = shuffler.finish_sequence()
        sequences.append(sequence)

    expected = [
        ["A-1", "A-2", "B-1", "B-2"],
        ["A-1", "B-1", "B-2", "A-2"],
        ["A-1", "B-1", "A-2", "B-2"],
        ["B-1", "A-1", "A-2", "B-2"],
        ["B-1", "A-1", "B-2", "A-2"],
        ["B-1", "B-2", "A-1", "A-2"],
    ]
    assert sorted(sequences) == sorted(expected)


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
async def test_exhaustive(ops_counts: list[int]) -> None:
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
    shuffler = AsyncioShuffler(pool_size=len(ops_counts), strategy=ExhaustiveStrategy())
    tasks, output = generate_tasks(shuffler, ops_counts)

    interleavings = []
    sequences = []
    while not shuffler.strategy_completed():
        await asyncio.gather(*(task() for task in tasks))
        interleavings.append(list(output))
        sequence = shuffler.finish_sequence()
        sequences.append(sequence)
        assert len(sequence) == len(output) == len(set(output)) == sum(ops_counts)
        output.clear()

    assert sorted(interleavings) == sorted(expected_interleavings)
    assert sorted(sequences) == sorted(expected_sequences)


@pytest.mark.parametrize(
    "ops_counts",
    (
        [1, 2],
        [1, 2, 3],
    ),
)
@pytest.mark.parametrize("n_iterations", [1, 2, 10])
async def test_random(
    ops_counts: list[int],
    n_iterations: int,
) -> None:
    shuffler = AsyncioShuffler(
        pool_size=len(ops_counts),
        strategy=RandomStrategy(max_iterations=n_iterations),
    )
    tasks, output = generate_tasks(shuffler, ops_counts)

    interleavings = []
    sequences = []
    while not shuffler.strategy_completed():
        await asyncio.gather(*(task() for task in tasks))
        interleavings.append(list(output))
        sequence = shuffler.finish_sequence()
        sequences.append(sequence)
        assert len(sequence) == len(output) == len(set(output)) == sum(ops_counts)
        output.clear()

    assert len(interleavings) == n_iterations


async def test_fuzzing() -> None:
    shuffler = AsyncioShuffler(
        pool_size=3,
        strategy=ExhaustiveStrategy(),
        max_wait_for=0.1,
    )

    async def fuzz() -> None:
        await asyncio.sleep(random.uniform(0, 0.002))

    async def task(task_id: str) -> None:
        await fuzz()
        async with shuffler.shuffle(f"{task_id}-1"):
            await fuzz()

        await fuzz()
        async with shuffler.shuffle(f"{task_id}-2"):
            await fuzz()

        await fuzz()
        shuffler.decrement_pool_size()

    sequences = []
    while not shuffler.strategy_completed():
        await asyncio.gather(task("A"), task("B"), task("C"))
        sequence = shuffler.finish_sequence()
        sequences.append(sequence)

    expected_sequences = all_interleavings(
        *([f"{task_id}-{op}" for op in (1, 2)] for task_id in "ABC")
    )
    assert sorted(sequences) == sorted(expected_sequences)
