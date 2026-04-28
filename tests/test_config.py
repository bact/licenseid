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
