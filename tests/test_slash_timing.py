# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The "/" reader stays linear (roadmap item 43): a run of slashes, spaces or
operands costs time in its length, never its square. Bounds have 10x
headroom over a laptop on `main` (CI's Python 3.10 runs under coverage); the
ratio test is a benchmark (`--run-benchmark`)."""
# pylint: disable=missing-function-docstring

import time
from collections.abc import Callable

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.resolveslash import slash_parts

SHAPES: dict[str, Callable[[int], str]] = {
    "operands": lambda n: "MIT/" * (n // 4 - 1) + "MIT",
    "slashes": lambda n: "/" * n,
    "space before": lambda n: "MIT" + " " * n + "/ISC",
    "space after": lambda n: "MIT/" + " " * n + "ISC",
    "tabs": lambda n: "MIT" + "\t" * n + "/\t" + "\t" * n + "ISC",
    "unknown": lambda n: "x/" * (n // 2),
}


def seconds(db: LicenseDatabase, text: str) -> float:
    start = time.monotonic()
    resolve(text, db)
    slash_parts(text, db)
    return time.monotonic() - start


@pytest.mark.parametrize("shape", SHAPES)
def test_a_long_value_is_read_in_time(corpus_db: LicenseDatabase, shape: str) -> None:
    assert seconds(corpus_db, SHAPES[shape](1990)) < 1.0


@pytest.mark.benchmark
@pytest.mark.parametrize("shape", SHAPES)
def test_time_grows_linearly(corpus_db: LicenseDatabase, shape: str) -> None:
    seconds(corpus_db, SHAPES[shape](200))  # warm the caches
    small = min(seconds(corpus_db, SHAPES[shape](500)) for _ in range(5))
    large = min(seconds(corpus_db, SHAPES[shape](2000)) for _ in range(5))
    assert large < 10 * max(small, 0.001) * 4
