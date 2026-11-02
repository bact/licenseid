# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, second round: a tag answers exact only what it read
whole, and the command line names what it refuses, on the whole 3.29.0
List.

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.cli import cli
from licenseid.detector import LicenseDetector


def _tag(corpus_db: LicenseDatabase, value: str) -> tuple[str, bool] | None:
    """The top answer of ``detect()`` for an SPDX tag of *value*."""
    found = LicenseDetector(corpus_db.location).detect(
        f"SPDX-License-Identifier: {value}"
    )
    return (found[0]["expression"], found[0]["exact"]) if found else None


# --- 1: a bare "or later" after an ID -----------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        # "later" was an ID ("MIT OR later", exact), or the grant dropped
        # ("MIT or-later" was MIT): the "or" is read as after a number, by
        # the one probe (classify.grant_end), as match() reads it (P35).
        ("MIT or later", "MIT+"),
        ("MIT OR LATER", "MIT+"),
        ("MIT, or later", "MIT+"),
        ("(MIT) or later", "MIT+"),  # match() refuses it; the tag reads
        ("MIT or later version", "MIT+"),  # the grant past brackets
        ("MIT or-later", "MIT+"),
        ("Apache-2.0 or later", "Apache-2.0+"),
        ("GPL-2.0 or later", "GPL-2.0-or-later"),
        ("MIT OR Apache-2.0", "Apache-2.0 OR MIT"),  # an operator stays one
        ("MIT or Apache-2.0", "Apache-2.0 OR MIT"),
    ],
)
def test_a_bare_grant_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    assert _tag(corpus_db, value) == (answer, True)


@pytest.mark.parametrize(
    "value",
    [
        "X OR later",
        "MIT OR Later-1.0",  # a word goes on: no grant, and no ID
        "MIT OR latex",
        "MIT+ or later",  # stated twice
        "GPL-2.0-only or later",
        "LicenseRef-a or later",
    ],
)
def test_no_word_that_is_no_id_answers_in_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _tag(corpus_db, value) is None


@pytest.mark.parametrize(
    ("value", "answer"),
    [("MIT or later", "MIT+"), ("MIT OR later", "MIT+"), ("MIT OR latex", None)],
)
def test_a_bare_grant_in_a_field(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, answer: str | None
) -> None:
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"name": "x", "license": value}), "utf-8")
    top = LicenseDetector(corpus_db.location).detect(file_path=str(manifest))[:1]
    assert next((r["expression"] for r in top if r["exact"]), None) == answer


# --- 2: an operand cut at a space ---------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        # Each was its first word, exact ("MIT OR Apache"); match() refuses
        # them (operand of several words), so the tag answers nothing.
        "MIT OR Apache 2.0",
        "MIT OR BSD 3-Clause",
        "MIT AND Apache License 2.0",
        "GPL v2 OR MIT",
        "MIT OR Foo-1.0",  # an ID the List does not have
        "MIT WITH Foo-exception",
    ],
)
def test_an_operand_that_is_no_listed_id_in_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _tag(corpus_db, value) is None


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("MIT OR LicenseRef-Apache", "MIT OR LicenseRef-Apache"),
        ("MIT OR DocumentRef-x:LicenseRef-y", "MIT OR DocumentRef-x:LicenseRef-y"),
        ("GPL-2.0-or-later WITH Classpath-exception-2.0", None),
        ("mit OR apache-2.0", "Apache-2.0 OR MIT"),  # any case of a listed ID
        ("MIT AND Apache-2.0", "Apache-2.0 AND MIT"),
    ],
)
def test_a_listed_id_or_a_reference_still_answers(
    corpus_db: LicenseDatabase, value: str, answer: str | None
) -> None:
    found = _tag(corpus_db, value)
    assert found is not None
    assert found == (answer or found[0], True)


# --- 3: an information separator given to detect ------------------------------


@pytest.mark.parametrize(
    ("args", "code", "stderr"),
    [
        # --text was blank (its own str.strip): it is text, no licence.
        (["--text", "\x1f"], 1, ""),
        (["--text", " \t"], 2, "ERROR: input: empty: --text\n"),
        # --id had an empty DETAIL: the value is named by its code points.
        (
            ["--id", "\x1f"],
            2,
            "ERROR: option: invalid: --id: U+001F; pass one license ID\n",
        ),
        (
            ["--id", "\x1c\x1c\x1d"],
            2,
            "ERROR: option: invalid: --id: U+001C U+001D; pass one license ID\n",
        ),
        (
            ["--id", "a b"],
            2,
            "ERROR: option: invalid: --id: a b; pass one license ID\n",
        ),
    ],
    ids=["text", "text-blank", "id", "id-several", "id-shown"],
)
def test_a_unit_separator_given_to_detect(
    corpus_db: LicenseDatabase, args: list[str], code: int, stderr: str
) -> None:
    result = CliRunner().invoke(cli, ["--db", corpus_db.location, "detect", *args])
    assert (result.exit_code, result.stderr) == (code, stderr)


@pytest.mark.parametrize("source", ["stdin", "file"])
def test_a_unit_separator_read_from_input(
    corpus_db: LicenseDatabase, tmp_path: Path, source: str
) -> None:
    """Standard input and a file were blank too (exit 2, ``empty``): text,
    no licence, as --text."""
    path = tmp_path / "x.txt"
    path.write_bytes(b"\x1f\n")
    args = ["-"] if source == "stdin" else [str(path)]
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "detect", *args], input="\x1f\n"
    )
    assert (result.exit_code, result.stderr) == (1, "")
