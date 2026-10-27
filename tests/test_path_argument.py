# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An argument that names no file: refused when it is shaped like a path,
matched when it is a URL or licence IDs joined by "/"."""
# pylint: disable=missing-function-docstring

import time
from collections.abc import Generator

import pytest
from click.testing import CliRunner
from matcher_db import Lic, seeded_db

from licenseid.cli import cli
from licenseid.textinput import looks_like_path

ROWS = (Lic("MIT", "MIT License"), Lic("Apache-2.0", "Apache License 2.0"))


@pytest.fixture(name="db_path")
def _db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_path_argument", ROWS)


@pytest.mark.parametrize("command", ["match", "is-osi"])
@pytest.mark.parametrize(
    "argument",
    [
        "COPYING.LESSER",  # an extension of more than five letters
        "LICENSE.markdown",
        "LICENSE.mp3",  # a digit after the first letter
        "MIT/",  # a part that names no licence
        "MIT/Foo",
        "./MIT",
        "../LICENSE",
    ],
)
def test_a_missing_path_is_refused(db_path: str, command: str, argument: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db_path, command, argument])
    assert result.exit_code == 2
    assert result.stdout == ""
    # the seeded database is old: its warning comes first
    last = result.stderr.splitlines()[-1]
    assert last == f"ERROR: input: not found: {argument}; pass --text"


@pytest.mark.parametrize(
    "argument",
    [
        "www.apache.org/licenses/LICENSE-2.0",  # a URL without its scheme
        "spdx.org/licenses/MIT.html",
        "opensource.org:443/licenses/MIT",
        "MIT/Apache-2.0",  # Cargo's old way to write OR
        "mit/apache-2.0",
        "MIT/LicenseRef-foo.txt",  # a LicenseRef may end in what looks like one
        "LicenseRef-foo.txt",
    ],
)
def test_a_url_or_licence_ids_are_no_path(db_path: str, argument: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db_path, "match", argument])
    assert "not found" not in result.stderr
    assert result.exit_code in (0, 1)


@pytest.mark.parametrize(
    ("value", "path"),
    [
        ("docs/LICENSE", True),
        ("LICENSE.md", True),
        ("x.TOML", True),
        ("Apache-2.0", False),  # a full stop before a version
        ("LPPL-1.3c", False),
        ("MIT.", False),
        ("MIT", False),
        ("example.com/x", False),
        ("a.b/x", True),  # one letter after the dot is no top-level domain
        ("example.com", True),  # a host alone, with no "/", reads as a file name
        ("http://x/y", False),
        ("docs/ LICENSE", False),
        ("", False),
    ],
)
def test_the_shape_of_a_path(value: str, path: bool) -> None:
    assert looks_like_path(value) is path


@pytest.mark.parametrize(
    "payload",
    ["a." * 50_000, "a-" * 50_000 + ".", "a." * 50_000 + "/"],
    ids=["dots", "hyphens", "dots-slash"],
)
def test_the_host_regex_does_not_backtrack(payload: str) -> None:
    start = time.monotonic()
    looks_like_path(payload)
    assert time.monotonic() - start < 1.0
