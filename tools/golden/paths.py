# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Put ``tests/`` on ``sys.path``, where the harness modules are (they are
not a package). Import this before any ``harness_*`` module."""

import sys
from pathlib import Path
from typing import Final

TESTS: Final = Path(__file__).resolve().parents[2] / "tests"

if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
