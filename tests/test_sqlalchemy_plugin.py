from typing import AsyncIterator

import pytest
from _pytest.fixtures import FixtureRequest
from sqlalchemy import Column, Integer, MetaData, Table, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from shuffler.plugins.sqlalchemy import AlchemyPlugin

meta = MetaData()

table = Table(
    "test",
    meta,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("value", Integer, nullable=False),
)


@pytest.fixture()
async def engine(request: FixtureRequest) -> AsyncIterator[AsyncEngine]:
    dsn = request.config.getoption("--db-dsn")
    assert dsn
    engine = create_async_engine(str(dsn))
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def setup_db(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)
        await conn.execute(table.delete())
        values = [{"id": 1, "value": 0}, {"id": 2, "value": 0}]
        await conn.execute(table.insert().values(values))

    yield

    async with engine.begin() as conn:
        await conn.run_sync(meta.drop_all)


async def increment(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        res = await conn.execute(select(table.c.value).where(table.c.id == 1))
        value = res.scalar_one()
        await conn.execute(table.update().values(value=value + 1))


async def reset(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(table.update().values(value=0))


async def get_value(engine: AsyncEngine) -> int:
    async with engine.begin() as conn:
        res = await conn.execute(select(table.c.value).where(table.c.id == 1))
        return int(res.scalar_one())


async def update_both(engine: AsyncEngine, first: int, second: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(table.update().where(table.c.id == first).values(value=1))
        await conn.execute(table.update().where(table.c.id == second).values(value=1))


@pytest.mark.db
async def test_lost_update(engine: AsyncEngine) -> None:
    plugin = AlchemyPlugin(engine=engine)

    results = []
    sequences = []
    async for sequence in plugin.run(
        lambda: increment(engine),
        lambda: increment(engine),
    ):
        value = await get_value(engine)
        results.append(value)
        sequences.append(sequence)

        await reset(engine)

    # 2 operations, each with 2 queries => 6 total interleavings (4! / (2! * 2!))
    assert len(results) == 6
    # 2/6 correct
    assert results.count(2) == 2
    # 4/6 racy
    assert results.count(1) == 4

    assert sorted(sequences) == sorted(
        [
            [1, 1, 2, 2],
            [2, 1, 1, 2],
            [1, 2, 1, 2],
            [1, 2, 2, 1],
            [2, 2, 1, 1],
            [2, 1, 2, 1],
        ]
    )


@pytest.mark.db
async def test_deadlock(engine: AsyncEngine) -> None:
    plugin = AlchemyPlugin(engine=engine)

    try:
        async for _ in plugin.run(
            lambda: update_both(engine, 1, 2),
            lambda: update_both(engine, 2, 1),
        ):
            pass
    except* DBAPIError as err:
        if "deadlock detected" not in str(err.exceptions):
            raise

    else:
        pytest.fail("Expected deadlock")
