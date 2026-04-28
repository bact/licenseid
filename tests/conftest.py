# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Shared test configuration and fixtures for licenseid.
"""

import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_spdx_tools_jar() -> Generator[None, None, None]:
    """Sets the SPDX_TOOLS_JAR environment variable to the bundled test jar."""
    jar_path = Path(__file__).parent / "tool.jar"
    if jar_path.exists():
        os.environ["SPDX_TOOLS_JAR"] = str(jar_path.absolute())
    yield


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options for pytest."""
    parser.addoption(
        "--run-benchmark",
        action="store_true",
        default=False,
        help="run benchmark tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "benchmark: mark test as a benchmark")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip benchmark tests by default."""
    if config.getoption("--run-benchmark"):
        # --run-benchmark given in cli: do not skip benchmark tests
        return
    skip_benchmark = pytest.mark.skip(reason="need --run-benchmark option to run")
    for item in items:
        if "benchmark" in item.keywords:
            item.add_marker(skip_benchmark)
