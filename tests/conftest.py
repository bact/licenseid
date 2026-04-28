# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_spdx_tools_jar():
    """Sets the SPDX_TOOLS_JAR environment variable to the bundled test jar."""
    jar_path = Path(__file__).parent / "tool.jar"
    if jar_path.exists():
        os.environ["SPDX_TOOLS_JAR"] = str(jar_path.absolute())
    yield
