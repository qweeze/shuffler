import asyncio
from typing import Iterator

import pytest

from shuffler.plugins.eventloop import EventLoopPlugin
from shuffler.util import n_interleavings


@pytest.fixture()
def plugin() -> Iterator[EventLoopPlugin]:
    plugin = EventLoopPlugin()
    yield plugin
    plugin.reset()


@pytest.fixture()
def event_loop_policy(plugin: EventLoopPlugin) -> asyncio.AbstractEventLoopPolicy:
    return plugin.event_loop_policy()


async def test_basic_case(plugin: EventLoopPlugin) -> None:
    output = []
    interleavings = set()

    async def task(task_id: str) -> None:
        output.append(f"{task_id}-1")
        await asyncio.sleep(0)
        output.append(f"{task_id}-2")

    while not plugin.strategy_completed():
        with plugin.activate():
            await asyncio.gather(task("A"), task("B"))

            interleavings.add(tuple(output))
            output.clear()

        plugin.finish_sequence()

    assert interleavings == {
        ("A-1", "B-1", "A-2", "B-2"),
        ("A-1", "B-1", "B-2", "A-2"),
        ("A-1", "A-2", "B-1", "B-2"),
        ("B-1", "A-1", "B-2", "A-2"),
        ("B-1", "B-2", "A-1", "A-2"),
        ("B-1", "A-1", "A-2", "B-2"),
    }


@pytest.mark.parametrize(
    "ops_counts",
    (
        [1, 3],
        [2, 2],
        [1, 2, 1],
    ),
)
async def test_interleavings(
    plugin: EventLoopPlugin,
    ops_counts: list[int],
) -> None:
    output = []
    interleavings = set()

    async def task(task_ix: int, n_ops: int) -> None:
        for n in range(n_ops):
            await asyncio.sleep(0)
            output.append(f"{task_ix}-{n}")

    while not plugin.strategy_completed():
        with plugin.activate():
            await asyncio.gather(
                *(task(task_ix, n_ops) for task_ix, n_ops in enumerate(ops_counts))
            )

            interleavings.add(tuple(output))
            output.clear()

        plugin.finish_sequence()

    assert len(interleavings) == n_interleavings(*ops_counts)
