# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A ``/`` in a manifest field (roadmap item 43): the license field of
package.json, pyproject.toml, Cargo.toml and setup.cfg holds a whole value, so
it answers what ``resolve()`` answers. A tag does not read a ``/`` (its value
can run on into prose: ``tests/test_spdx_tag_adversarial.py``)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from test_manifest_license import MANIFESTS, manifest

from licenseid import resolve
from licenseid.detector import LicenseDetector

ROWS = [
    Lic("MIT", "MIT License", True, True, True, search_text="mit license"),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True, search_text="apache"),
    Lic("ISC", "ISC License", True, True, True, search_text="isc license"),
    Lic("Zlib", "zlib License", True, True, True, search_text="zlib license"),
    Lic("Libpng", "PNG Reference Library License v1", search_text="libpng"),
]


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    yield from seeded_db("test_slash_fields", ROWS)


def top_of(db: str, path: str) -> str | None:
    found = LicenseDetector(db).detect(file_path=path)
    return found[0]["expression"] if found else None


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", list(MANIFESTS))
@pytest.mark.parametrize(
    "value",
    ["MIT/Apache-2.0", "Apache-2.0/MIT", "MIT / Apache-2.0", "MIT/ISC/Zlib"],
)
def test_a_field_reads_ids_joined_by_a_slash_as_or(
    db: str, tmp_path: Path, kind: str, large: bool, value: str
) -> None:
    path = manifest(tmp_path, kind, value, large)
    expression = resolve(value, db)["expression"]
    assert expression is not None and " OR " in expression
    assert top_of(db, path) == expression


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", list(MANIFESTS))
@pytest.mark.parametrize(
    "value",
    ["zlib/libpng", "mit/apache-2.0", "MIT/Apache", "MIT//ISC", "MIT/X11", "TCL/TK"],
)
def test_a_field_does_not_read_what_resolve_refuses(
    db: str, tmp_path: Path, kind: str, large: bool, value: str
) -> None:
    path = manifest(tmp_path, kind, value, large)
    assert resolve(value, db)["expression"] is None
    assert top_of(db, path) not in {"Libpng OR Zlib", "Apache-2.0 OR MIT", "ISC OR MIT"}


@pytest.mark.parametrize("tag", ["MIT/Apache-2.0", "MIT / Apache-2.0", "MIT/ISC"])
def test_a_tag_does_not_read_a_slash(db: str, tmp_path: Path, tag: str) -> None:
    path = tmp_path / "source.py"
    path.write_text(f"# SPDX-License-Identifier: {tag}\n", encoding="utf-8")
    found = LicenseDetector(db).detect(file_path=str(path))
    assert [r["expression"] for r in found if " OR " in r["expression"]] == []
