# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Combination matrix for ``licenseid update``: every ``--source`` x
``--cache/--no-cache`` x ``--list`` x ``--force``, each run twice on one
database, so an option is never only tested on its own (AGENTS.md
"Testing"; the ``detect`` and ``is-*`` axes are in test_option_matrix.py).

The world: the network serves version 9.99 from every source, and the
snapshot shipped in the wheel is 9.98."""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import update_line
from release_fakes import online, release_bundle, serve, ship, urls

from licenseid.cli import cli

SOURCES = ["auto", "compact", "upstream", "packaged"]
CACHES = ["--cache", "--no-cache"]
# None: no --list; "": --list spdx-license-list, at its latest; else at it.
VERSIONS = [None, "", "9.99", "9.98"]
PACKAGED = "9.98"
LIST = "spdx-license-list"


def _expected(source: str, version: str | None) -> tuple[str | None, str]:
    """``(installed version, data source)`` of a first run, or ``(None,
    error)`` when it fails."""
    version = version or None  # the list named with no version: the latest
    if source == "packaged":
        if version in (None, PACKAGED):
            return PACKAGED, "packaged"
        return None, f"spdx-bundle.json.gz: not found: version {version}"
    if version == PACKAGED:  # the network has no 9.98
        if source == "auto":
            return PACKAGED, "packaged"
        name = "spdx-bundle" if source == "compact" else "spdx-data"
        return None, f"{name}-v9.98."
    return "9.99", "upstream (remote)" if source == "upstream" else "compact (remote)"


def _run(db: Path, args: list[str]) -> Result:
    return CliRunner().invoke(cli, ["--db", str(db), "update", *args])


def _data_source(stderr: str) -> str:
    line = next(line for line in stderr.splitlines() if "License List data " in line)
    return line.split(" : ")[1]


def _second_source(source: str, version: str | None, cache: str) -> str:
    """The data source of a forced second run."""
    first = _expected(source, version)[1]
    if cache == "--cache" and first.endswith("(remote)"):
        return first.replace("(remote)", "(cache)")
    return first


@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
@pytest.mark.parametrize("force", [False, True], ids=["plain", "force"])
@pytest.mark.parametrize(
    "version", VERSIONS, ids=lambda v: "no-list" if v is None else v or "latest"
)
@pytest.mark.parametrize("cache", CACHES)
@pytest.mark.parametrize("source", SOURCES)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_update_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    cache: str,
    version: str | None,
    force: bool,
    as_json: bool,
) -> None:
    fake = serve(monkeypatch, online())
    ship(monkeypatch, release_bundle(PACKAGED))
    db = tmp_path / "licenses.db"
    args = ["--source", source, cache]
    if version is not None:
        args += ["--list", f"spdx-license-list@{version}" if version else LIST]
    args += ["--force"] if force else []
    args += ["--json"] if as_json else []
    installed, detail = _expected(source, version)

    first = _run(db, args)
    if version:  # C2: a version given is never looked up, even on a failure
        assert not [u for u in urls(fake) if u.endswith("latest.json")]
    if installed is None:
        assert first.exit_code == 1, first.output
        assert first.stdout == ""
        assert first.stderr.splitlines()[-1].startswith(f"ERROR: {detail}")
        assert _run(db, args).exit_code == 1  # no state that hides the failure
        return
    assert first.exit_code == 0, first.output
    assert first.stdout == update_line("updated", installed, db, as_json=as_json)
    assert _data_source(first.stderr) == detail
    if source == "packaged":
        fake.assert_not_called()

    fake.reset_mock()
    second = _run(db, args)
    assert second.exit_code == 0, second.output
    if force:
        assert second.stdout == update_line("updated", installed, db, as_json=as_json)
        assert _data_source(second.stderr) == _second_source(source, version, cache)
    else:
        assert second.stdout == update_line("unchanged", installed, db, as_json=as_json)
    if source == "packaged":
        fake.assert_not_called()
    elif cache == "--cache" and installed != PACKAGED:
        # A fresh version cache and a cached compact or upstream file: no
        # download.
        assert urls(fake) == []
