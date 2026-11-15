# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect --variant`` x input source x found / not found (an axis of
``tests/test_option_matrix.py``, kept apart for its size). MIT has no variant,
so each value answers it alike; a value that is no variant is a usage error."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import NO_DETECTION, make_mit_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import MIT_TEXT

from licenseid.cli import cli

pytestmark = pytest.mark.terse_cli  # the matrix names --verbose itself

VARIANTS = ["auto", "as-written", "only", "or-later"]
SOURCES = ["arg_id", "arg_file", "text", "id", "stdin"]


@pytest.fixture
def mit_db() -> Generator[str, None, None]:
    db_path, keep_alive = make_mit_db_path(
        "test_matrix_variant", datetime.now(timezone.utc).isoformat()
    )
    yield db_path
    keep_alive.close()


def _source_args(source: str, found: bool, tmp_path: Path) -> tuple[list[str], str]:
    text = MIT_TEXT if found else "Nothing like a licence appears in this line."
    license_id = "MIT" if found else "Nope-1.0"
    path = tmp_path / "LICENSE"
    path.write_text(text, encoding="utf-8")
    if source == "arg_file":
        return [str(path)], ""
    if source == "stdin":
        return [], text
    flag = "--id" if source == "id" else "--text"
    return (
        [license_id]
        if source == "arg_id"
        else [flag, text if flag == "--text" else license_id]
    ), ""


@pytest.mark.parametrize("found", [True, False], ids=["found", "not_found"])
@pytest.mark.parametrize("variant", [*VARIANTS, "nope"])
@pytest.mark.parametrize("source", SOURCES)
def test_variant_matrix(
    mit_db: str, tmp_path: Path, source: str, variant: str, found: bool
) -> None:
    args, stdin = _source_args(source, found, tmp_path)
    result = CliRunner().invoke(
        cli,
        ["--db", mit_db, "detect", "--verbose", "--variant", variant, *args],
        input=stdin,
    )
    if variant == "nope":
        assert (result.exit_code, result.stdout) == (2, "")
        assert result.stderr.startswith("ERROR: option: invalid: --variant: nope")
    elif not found:
        assert (result.exit_code, result.stdout) == (1, NO_DETECTION)
    else:
        assert (result.exit_code, result.stderr) == (0, "")
        first = result.stdout.splitlines()[0]
        assert first.startswith("EXPRESSION=MIT\t")
        assert first.endswith("VARIANT_STATED=")
