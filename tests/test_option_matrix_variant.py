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
from click.testing import CliRunner, Result
from conftest import NO_DETECTION, FoundRows, make_mit_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import MIT_TEXT
from matcher_db import GPL2_ROWS, Lic, seeded_db
from texts_db import GPL as GPL_TEXT
from texts_db import A, texts_database

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
        # An exact text holds its own text, short as it is; a value, none.
        texts = "MIT" if "\tMETHOD=text\t" in first else ""
        assert first.endswith(f"VARIANT_STATED=\tSAME_TEXT=\tREASON=\tTEXTS={texts}")


@pytest.fixture(scope="module")
def gpl_db() -> Generator[str, None, None]:
    yield from seeded_db("test_matrix_variant_gpl", GPL2_ROWS, [])


# (variant, value) -> (expression, VARIANT_STATED, a warning is said)
GPL = {
    ("auto", "GPL-2.0"): ("GPL-2.0", "false", False),
    ("as-written", "GPL-2.0"): ("GPL-2.0", "false", False),
    ("only", "GPL-2.0"): ("GPL-2.0-only", "false", True),
    ("or-later", "GPL-2.0"): ("GPL-2.0-or-later", "false", True),
    ("auto", "GPL-2.0 or later"): ("GPL-2.0-or-later", "true", False),
    ("as-written", "GPL-2.0 or later"): ("GPL-2.0-or-later", "true", False),
    ("only", "GPL-2.0 or later"): ("GPL-2.0-or-later", "true", True),  # overridden
    ("or-later", "GPL-2.0 or later"): ("GPL-2.0-or-later", "true", False),
    ("auto", "GPL-2.0-only"): ("GPL-2.0-only", "true", False),
    ("as-written", "GPL-2.0-only"): ("GPL-2.0-only", "true", False),
    ("only", "GPL-2.0-only"): ("GPL-2.0-only", "true", False),
    ("or-later", "GPL-2.0-only"): ("GPL-2.0-only", "true", True),  # overridden
}


@pytest.mark.parametrize("source", ["arg_id", "arg_file", "text", "stdin"])
@pytest.mark.parametrize(("variant", "value"), list(GPL))
def test_variant_matrix_gpl_family(
    gpl_db: str, tmp_path: Path, source: str, variant: str, value: str
) -> None:
    """Every ``--variant`` x a GPL-family value x input source: the answer,
    ``VARIANT_STATED`` and whether a warning is said."""
    path = tmp_path / "LICENSE"
    path.write_text(value + "\n", encoding="utf-8")
    args, stdin = {
        "arg_id": ([value], ""),
        "arg_file": ([str(path)], ""),
        "text": (["--text", value], ""),
        "stdin": ([], value),
    }[source]
    result = CliRunner().invoke(
        cli,
        ["--db", gpl_db, "detect", "--verbose", "--variant", variant, *args],
        input=stdin,
    )
    expression, stated, said = GPL[variant, value]
    assert result.exit_code == 0, result.stderr
    first = result.stdout.splitlines()[0]
    assert first.startswith(f"EXPRESSION={expression}\t")
    assert first.endswith(f"VARIANT_STATED={stated}\tSAME_TEXT=\tREASON=\tTEXTS=")
    warned = [x for x in result.stderr.splitlines() if "days old" not in x]
    assert bool(warned) is said, warned


LGPL_ROWS = (
    Lic("LGPL-2.0-only", "GNU Library General Public License v2 only", True, True),
    Lic("LGPL-2.0-or-later", "GNU Library General Public License v2 or later"),
    Lic("LGPL-2.0", "GNU Library General Public License v2", False, is_deprecated=True),
    Lic("LGPL-2.1-only", "GNU Lesser General Public License v2.1 only", True, True),
    Lic("LGPL-2.1-or-later", "GNU Lesser General Public License v2.1 or later"),
    Lic(
        "LGPL-2.1", "GNU Lesser General Public License v2.1", False, is_deprecated=True
    ),
)


@pytest.fixture(scope="module")
def lgpl_db() -> Generator[str, None, None]:
    yield from seeded_db("test_matrix_variant_lgpl", LGPL_ROWS, [])


# (variant, value) -> expression, or None for no answer (item 54): `LGPLv2`
# writes only the major, and the List has 2.0 and 2.1, whatever the variant
# says; a grant covers every later minor, so `LGPLv2+` is answered.
LGPL: dict[tuple[str, str], str | None] = {
    **{(v, "LGPLv2"): None for v in VARIANTS},
    ("as-written", "LGPL-2.1"): "LGPL-2.1",
    ("auto", "LGPLv2+"): "LGPL-2.0-or-later",
    ("or-later", "LGPLv2+"): "LGPL-2.0-or-later",
    ("only", "LGPLv2 or later"): "LGPL-2.0-or-later",  # overridden by the input
}


@pytest.mark.parametrize("source", ["arg_id", "text", "stdin"])
@pytest.mark.parametrize(("variant", "value"), list(LGPL))
def test_variant_matrix_cut_major(
    lgpl_db: str, source: str, variant: str, value: str
) -> None:
    """A bare major with another minor on the List gets no answer under every
    ``--variant`` and input source; a grant on it is answered."""
    args, stdin = {
        "arg_id": ([value], ""),
        "text": (["--text", value], ""),
        "stdin": ([], value),
    }[source]
    result = CliRunner().invoke(
        cli,
        ["--db", lgpl_db, "detect", "--verbose", "--variant", variant, *args],
        input=stdin,
    )
    expression = LGPL[variant, value]
    if expression is None:
        assert (result.exit_code, result.stdout) == (1, NO_DETECTION)
    else:
        assert result.exit_code == 0, result.stderr
        assert result.stdout.splitlines()[0].startswith(f"EXPRESSION={expression}\t")


# TEXTS names the texts an input holds by the variant in force (made-up texts:
# the answer's own is A-1.0's, and the GPL-3.0 pair shares one).
@pytest.fixture
def texts_db() -> Generator[str, None, None]:
    yield from texts_database("test_matrix_variant_texts")


def _fields(result: Result) -> dict[str, str]:
    line = result.stdout.splitlines()[0]
    return dict(f.partition("=")[::2] for f in line.split("\t"))


# variant -> how a group other than the answer's is named
OTHER_FAMILY = {
    "auto": "GPL-3.0-only",
    "only": "GPL-3.0-only",
    "or-later": "GPL-3.0-or-later",
    "as-written": "GPL-3.0-only",
}


@pytest.mark.parametrize("variant", VARIANTS)
def test_texts_names_another_family_as_the_variant_names_it(
    texts_db: str, found_rows: FoundRows, variant: str
) -> None:
    found_rows.rows = ["A-1.0", "GPL-3.0-only"]
    result = CliRunner().invoke(
        cli,
        ["--db", texts_db, "detect", "-v", "--variant", variant, "--text", A + " x"],
    )
    assert result.exit_code == 0, result.stderr
    fields = _fields(result)
    assert fields["EXPRESSION"] == "A-1.0"
    assert fields["TEXTS"] == f"A-1.0 {OTHER_FAMILY[variant]}"


@pytest.mark.parametrize("variant", VARIANTS)
def test_texts_names_the_answers_family_as_the_answer(
    texts_db: str, found_rows: FoundRows, variant: str
) -> None:
    found_rows.rows = ["GPL-3.0-only"]
    result = CliRunner().invoke(
        cli,
        [
            "--db",
            texts_db,
            "detect",
            "-v",
            "--variant",
            variant,
            "--text",
            GPL_TEXT + " x",
        ],
    )
    fields = _fields(result)
    assert fields["EXPRESSION"] == (
        "GPL-3.0-or-later" if variant == "or-later" else "GPL-3.0-only"
    )
    assert fields["TEXTS"] == fields["EXPRESSION"]
    # One search, with no answer: it found the answer's text alone, so it
    # stands for the answer's (licenseid.textcandidates).
    assert [answer for _, answer in found_rows.calls] == [""]


def test_texts_of_a_declared_value_is_empty_under_every_variant(
    texts_db: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0"]
    for variant in VARIANTS:
        result = CliRunner().invoke(
            cli,
            ["--db", texts_db, "detect", "-v", "--variant", variant, "GPL-3.0"],
        )
        assert _fields(result)["TEXTS"] == ""
    assert not found_rows.calls
