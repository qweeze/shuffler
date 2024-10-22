import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.python import Function


def pytest_configure(config: Config) -> None:
    config.addinivalue_line("markers", "db: mark test to run only with a DB set up")


def pytest_addoption(parser: Parser) -> None:
    parser.addoption("--db-dsn", action="store", default=None)


def pytest_collection_modifyitems(config: Config, items: list[Function]) -> None:
    if config.getoption("--db-dsn") is None:
        for item in items:
            if "db" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Pass --db-dsn option to run"))
