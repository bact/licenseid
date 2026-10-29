# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The sdist ships an allowlist (``only-include`` in pyproject.toml): a new
entry there is a decision, so it is pinned here."""

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SHIPPED = {
    "CHANGELOG.md",
    "CITATION.cff",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "codemeta.json",
    "docs",
    "hatch_build.py",
    "src",
}


def _sdist_table() -> dict[str, object]:
    tomllib = pytest.importorskip("tomllib")  # Python 3.11 and later
    with (ROOT / "pyproject.toml").open("rb") as file:
        config = tomllib.load(file)
    table: dict[str, object] = config["tool"]["hatch"]["build"]["targets"]["sdist"]
    return table


def test_the_sdist_ships_only_the_allowlist() -> None:
    """Only the listed entries, and no exclude list beside them."""
    table = _sdist_table()
    entries = table.get("only-include")
    assert set(table) == {"only-include"}
    assert isinstance(entries, list)
    assert set(entries) == SHIPPED


@pytest.mark.parametrize("entry", sorted(SHIPPED))
def test_every_shipped_entry_exists(entry: str) -> None:
    """A renamed file would drop out of the sdist without an error."""
    assert (ROOT / entry).exists()
