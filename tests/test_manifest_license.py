# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The license field of a package manifest, end to end, and the SPDX flags
on every result. Roadmap item 18."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import MIT_SEARCH_TEXT
from matcher_db import Lic, seeded_db

from licenseid.cli import cli
from licenseid.manifest import toml_license_values
from licenseid.matcher import AggregatedLicenseMatcher

FILLER = (
    "A widget scheduler that keeps a queue of pending widgets and dispatches"
    " them to worker threads in arrival order, retrying transient failures a"
    " few times before giving up and reporting an error to the caller"
)

# A small manifest has fewer than 30 words, the Tier 0 threshold; FILLER
# takes each past it.
MANIFESTS: dict[str, tuple[str, str]] = {
    "package-json": (
        "package.json",
        '{{"name": "x", "version": "1.0.0", {extra}"license": "{value}"}}',
    ),
    "pyproject-table": (
        "pyproject.toml",
        '[project]\nname = "x"\n{extra}license = {{text = "{value}"}}\n',
    ),
    "pyproject-string": (
        "pyproject.toml",
        '[project]\nname = "x"\n{extra}license = "{value}"\n',
    ),
    "poetry": (
        "pyproject.toml",
        '[tool.poetry]\nname = "x"\n{extra}license = "{value}"\n',
    ),
    "cargo": (
        "Cargo.toml",
        '[package]\nname = "x"\nedition = "2021"\n{extra}license = "{value}"\n',
    ),
    "setup-cfg": ("setup.cfg", "[metadata]\nname = x\n{extra}license = {value}\n"),
}


def extra_field(kind: str) -> str:
    if kind == "package-json":
        return f'"description": "{FILLER}", '
    if kind == "setup-cfg":
        return f"description = {FILLER}\n"
    return f'description = "{FILLER}"\n'


def manifest(tmp_path: Path, kind: str, value: str, large: bool) -> str:
    name, template = MANIFESTS[kind]
    extra = extra_field(kind) if large else ""
    path = tmp_path / name
    path.write_text(template.format(extra=extra, value=value), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    rows = [
        Lic("MIT", "MIT License", True, True, True, search_text=MIT_SEARCH_TEXT),
        Lic("Apache-2.0", "Apache License 2.0", True, True, True, search_text="x"),
        Lic("Apache-1.0", "Apache License 1.0", True, False, True, search_text="y"),
        Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True, True),
        Lic(
            "GPL-2.0-with-GCC-exception",
            "GNU General Public License v2.0 w/GCC Runtime Library exception",
            is_deprecated=True,
        ),
    ]
    yield from seeded_db("test_manifest_license", rows, ["GCC-exception-2.0"])


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", list(MANIFESTS))
def test_a_manifest_expression_is_certain(
    db: str, tmp_path: Path, kind: str, large: bool
) -> None:
    """A small manifest used to be matched by name (Apache-1.0 at 1.01); a
    TOML or INI field scored 0.902 with no flags, so is_spdx() said False."""
    path = manifest(tmp_path, kind, "MIT OR Apache-2.0", large)
    matcher = AggregatedLicenseMatcher(db)
    top = matcher.match(file_path=path)[0]
    assert (top["license_id"], top["score"]) == ("Apache-2.0 OR MIT", 1.0)
    # OSI and FSF approval has no plain meaning for an OR (flag_source).
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        False,
        False,
    )
    assert matcher.is_spdx(file_path=path)


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", list(MANIFESTS))
def test_a_manifest_license_id_carries_its_flags(
    db: str, tmp_path: Path, kind: str, large: bool
) -> None:
    path = manifest(tmp_path, kind, "Apache-2.0", large)
    matcher = AggregatedLicenseMatcher(db)
    top = matcher.match(file_path=path)[0]
    assert (top["license_id"], top["score"]) == ("Apache-2.0", 1.0)
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        True,
        True,
    )
    assert matcher.is_osi(file_path=path)
    assert matcher.is_fsf(file_path=path)


FLAGS = ("is_spdx", "is_osi_approved", "is_fsf_libre")


@pytest.mark.parametrize(
    "text",
    [
        "MIT",  # Tier 0, an ID
        "MIT License",  # Tier 0, a name
        MIT_SEARCH_TEXT,  # Tier 2, the license text
    ],
    ids=["id", "name", "text"],
)
def test_every_result_carries_the_flags(db: str, text: str) -> None:
    results = AggregatedLicenseMatcher(db).match(text=text)
    assert results
    for result in results:
        assert all(isinstance(result.get(flag), bool) for flag in FLAGS), result
    assert results[0]["license_id"] == "MIT"
    assert all(results[0].get(flag) for flag in FLAGS)


def test_a_deprecated_id_takes_the_flags_of_its_replacement(db: str) -> None:
    """GPL-2.0-with-GCC-exception answers GPL-2.0-only WITH GCC-exception-2.0,
    an expression: its flags are the license's, not "unknown"."""
    matcher = AggregatedLicenseMatcher(db)
    top = matcher.match(text="GPL-2.0-with-GCC-exception")[0]
    assert top["license_id"] == "GPL-2.0-only WITH GCC-exception-2.0"
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        True,
        True,
    )
    assert matcher.is_spdx("GPL-2.0-with-GCC-exception")
    assert matcher.is_osi("GPL-2.0-with-GCC-exception")


def test_match_json_shows_the_flags_of_a_manifest(db: str, tmp_path: Path) -> None:
    path = manifest(tmp_path, "pyproject-string", "MIT OR Apache-2.0", large=False)
    result = CliRunner().invoke(cli, ["--db", db, "match", "--json", path])
    assert result.exit_code == 0, result.output
    top = json.loads(result.stdout)[0]
    assert {flag: top[flag] for flag in FLAGS} == {
        "is_spdx": True,
        "is_osi_approved": False,
        "is_fsf_libre": False,
    }


def test_is_spdx_answers_yes_for_a_toml_expression(db: str, tmp_path: Path) -> None:
    """It answered false: the field scored 0.902, with no flags."""
    path = manifest(tmp_path, "pyproject-table", "MIT OR Apache-2.0", large=True)
    result = CliRunner().invoke(cli, ["--db", db, "is-spdx", path])
    assert (result.exit_code, result.stdout) == (0, "true\n")


def test_a_manifest_declares_one_license_per_table() -> None:
    """Each value costs a database lookup, so a file of thousands of license
    lines yields one value per form and table."""
    text = (
        '[project]\nlicense = "A"\nlicense = "B"\n'
        '[package]\nlicense = "C"\n[project]\nlicense = "D"\n'
    )
    assert toml_license_values(text) == ["A", "C"]
