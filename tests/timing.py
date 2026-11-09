# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The time bound of a test that guards against a quadratic scan.

A bound is written for a quiet laptop. CI runs the suite under ``coverage``
(plain Python runs several times slower with tracing on) and in parallel
workers (``pytest -n``), so :func:`slack` scales the bound by the same
factor the work slows by: a quadratic scan stays far over it, a slow
runner does not trip it. Never use it for a ratio of two sizes.
"""

import os
from typing import Final

import coverage

#: How much slower plain Python runs with ``coverage`` tracing on.
UNDER_COVERAGE: Final[float] = 4.0
#: How much slower a test runs beside the other workers of ``pytest -n``.
UNDER_XDIST: Final[float] = 2.0


def slack(seconds: float) -> float:
    """Return *seconds*, scaled for tracing and for parallel workers."""
    factor = 1.0
    if coverage.Coverage.current() is not None:
        factor *= UNDER_COVERAGE
    if os.environ.get("PYTEST_XDIST_WORKER"):
        factor *= UNDER_XDIST
    return seconds * factor
