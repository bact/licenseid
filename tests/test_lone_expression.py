# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A lone SPDX expression answers alike through every channel. Roadmap
item 21: as text, Tier 0 read the normalised value, which has lost its "+",
so --text GPL-2.0+ answered GPL-2.0-only."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import json_lines
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.cli import cli
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    rows = [
        *GPL2_ROWS,
        # Flags that tell the two apart (not the License List's).
        Lic(
            "LGPL-2.1-only",
            "GNU Lesser General Public License v2.1 only",
            True,
            True,
            True,
        ),
        Lic("LGPL-2.1-or-later", "GNU Lesser General Public License v2.1 or later"),
        Lic("LGPL-2.1", "GNU Lesser General Public License v2.1", is_deprecated=True),
        Lic("Apache-2.0", "Apache License 2.0", True, True, True),
        Lic("MIT", "MIT License", True, True, True),
        Lic("Fair-1.0", "Fair-Play"),
        Lic(
            "GFDL-1.3-only",
            "GNU Free Documentation License v1.3 only",
            True,
            False,
            True,
        ),
        Lic(
            "GFDL-1.3-or-later",
            "GNU Free Documentation License v1.3 or later",
            True,
            False,
            True,
        ),
        # The deprecated row's own flags differ from those of the -only form.
        Lic("GFDL-1.3", "GNU Free Documentation License v1.3", is_deprecated=True),
    ]
    yield from seeded_db("test_lone_expression", rows, ["Classpath-exception-2.0"])


def _api(db: str, value: str, tmp_path: Path, channel: str) -> list[str]:
    matcher = AggregatedLicenseMatcher(db)
    if channel == "file":
        path = tmp_path / "LICENSE"
        path.write_text(f"{value}\n", encoding="utf-8")
        results = matcher.match(file_path=str(path))
    elif channel == "id":
        results = matcher.match(license_id=value)
    else:
        results = matcher.match(text=value)
    return [r["license_id"] for r in results if r["score"] >= 0.85]


def _cli(db: str, value: str, tmp_path: Path, channel: str) -> list[str]:
    args, stdin = {
        "argument": ([value], None),
        "text": (["--text", value], None),
        "stdin": ([], value),
        "id": (["--id", value], None),
        "file": ([str(tmp_path / "LICENSE")], None),
    }[channel]
    (tmp_path / "LICENSE").write_text(f"{value}\n", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--db", db, "match", "--json", *args], stdin)
    assert result.exit_code == 0, result.output
    return [r["license_id"] for r in json_lines(result.stdout)]


CHANNELS = [
    *(f"api-{how}" for how in ("text", "file", "id")),
    *(f"cli-{how}" for how in ("argument", "text", "stdin", "file", "id")),
]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("GPL-2.0+", "GPL-2.0-or-later"),
        ("(LGPL-2.1+)", "LGPL-2.1-or-later"),
        (
            "GPL-2.0+ WITH Classpath-exception-2.0",
            "GPL-2.0-or-later WITH Classpath-exception-2.0",
        ),
        # No -or-later ID: the "+" stays.
        ("Apache-2.0+", "Apache-2.0+"),
        (
            "LicenseRef-x WITH Classpath-exception-2.0",
            "LicenseRef-x WITH Classpath-exception-2.0",
        ),
        ("GPL-2.0", "GPL-2.0-only"),
        # GFDL had no redirect: GFDL-1.3+ answered itself.
        ("GFDL-1.3+", "GFDL-1.3-or-later"),
        ("GFDL-1.3", "GFDL-1.3-only"),
    ],
)
@pytest.mark.parametrize("channel", CHANNELS)
def test_a_lone_expression_answers_alike_in_every_channel(
    db: str, tmp_path: Path, value: str, expected: str, channel: str
) -> None:
    source, how = channel.split("-")
    read = _api if source == "api" else _cli
    assert read(db, value, tmp_path, how) == [expected]


@pytest.mark.parametrize("command", ["is-osi", "is-fsf"])
@pytest.mark.parametrize("args", [["--text"], []], ids=["text", "argument"])
def test_a_lone_expression_is_judged_as_its_id(
    db: str, command: str, args: list[str]
) -> None:
    """LGPL-2.1-or-later has neither flag here; LGPL-2.1-only has both."""
    result = CliRunner().invoke(cli, ["--db", db, command, *args, "LGPL-2.1+"])
    assert (result.exit_code, result.stdout) == (1, "false\n")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Shaped like an ID but none: the name match reads it, as before,
        # and finds the name exactly.
        ("Fair.Play", [("Fair-1.0", "name", 1.0, 1.0)]),
        # Not SPDX-shaped, so Tier 0 still drops the "+" (roadmap item 30).
        ("GPL 2.0+", [("GPL-2.0-only", "id", 1.0, None)]),
    ],
)
def test_any_other_value_is_read_as_text(
    db: str, value: str, expected: list[tuple[str, str, float, float | None]]
) -> None:
    results = AggregatedLicenseMatcher(db).match(text=value)
    assert [
        (r["license_id"], r["method"], r["score"], r["similarity"]) for r in results
    ] == expected
    assert all(r["exact"] for r in results)


def test_a_deprecated_gfdl_id_has_the_flags_of_its_successor(db: str) -> None:
    """GFDL-1.3 answered itself, with the deprecated row's flags."""
    result = CliRunner().invoke(cli, ["--db", db, "is-fsf", "--text", "GFDL-1.3"])
    assert (result.exit_code, result.stdout) == (0, "true\n")


def test_a_license_ref_with_a_plus_is_no_license(db: str) -> None:
    """SPDX gives "+" to a license ID only. It answered LicenseRef-x+ as a
    valid SPDX license; as --id it is no single license, a usage error."""
    assert not AggregatedLicenseMatcher(db).match(text="LicenseRef-x+")
    result = CliRunner().invoke(cli, ["--db", db, "match", "--id", "LicenseRef-x+"])
    assert result.exit_code == 2
