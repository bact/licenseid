# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect`` says why a record has no answer: the last field ``REASON``
(JSON ``reason``) is ``below threshold``, ``not exact`` or ``no match``, and
empty (``null``) on an answer. The tests see the command line as written."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner
from conftest import MIT_SEARCH_TEXT, make_mit_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid.cli import cli

pytestmark = pytest.mark.terse_cli

# MIT's words, two of them changed: a close text, an answer but not exact.
CLOSE = MIT_SEARCH_TEXT.replace("granted", "given").replace("person", "human")
# Words no licence holds: Tier 1 finds no candidate.
GIBBERISH = " ".join(f"zqx{n}vk" for n in range(15))


@pytest.fixture
def db() -> Generator[str, None, None]:
    path, keep_alive = make_mit_db_path(
        "test_reason", datetime.now(timezone.utc).isoformat()
    )
    yield path
    keep_alive.close()


def record(db_path: str, *args: str) -> tuple[int, dict[str, str]]:
    """The exit code and the fields of the one verbose line."""
    result = CliRunner().invoke(cli, ["--db", db_path, "detect", "-v", *args])
    (line,) = result.stdout.splitlines()
    return result.exit_code, dict(f.split("=", 1) for f in line.split("\t"))


def test_the_last_field_is_the_reason(db: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db, "detect", "-v", "--id", "MIT"])
    assert result.stdout.rstrip("\n").split("\t")[-1] == "REASON="


def test_an_answer_has_no_reason(db: str) -> None:
    assert record(db, "--text", MIT_SEARCH_TEXT + " " + "x")[1]["REASON"] == ""
    code, fields = record(db, "--id", "MIT")
    assert (code, fields["REASON"]) == (0, "")


def test_nothing_found_is_no_match(db: str) -> None:
    code, fields = record(db, "--text", GIBBERISH)
    assert (code, fields["EXPRESSION"], fields["REASON"]) == (1, "", "no match")


def test_a_weak_text_under_a_high_threshold_is_below_threshold(db: str) -> None:
    code, fields = record(db, "--threshold", "0", "--text", CLOSE)
    assert (code, fields["EXPRESSION"]) == (0, "MIT")
    assert float(fields["SCORE"]) < 0.99
    code, fields = record(db, "--threshold", "0.99", "--text", CLOSE)
    assert (code, fields["EXPRESSION"], fields["REASON"]) == (
        1,
        "",
        "below threshold",
    )


def test_exact_that_removes_every_result_is_not_exact(db: str) -> None:
    code, fields = record(db, "--threshold", "0", "--text", CLOSE)
    assert (code, fields["EXACT"]) == (0, "false")
    code, fields = record(db, "--threshold", "0", "--exact", "--text", CLOSE)
    assert (code, fields["EXPRESSION"], fields["REASON"]) == (1, "", "not exact")


def test_threshold_is_named_before_exact(db: str) -> None:
    __, fields = record(db, "--threshold", "0.99", "--exact", "--text", CLOSE)
    assert fields["REASON"] == "below threshold"


def test_a_missing_id_is_no_match(db: str) -> None:
    assert record(db, "--id", "No-Such-1.0")[1]["REASON"] == "no match"


def test_json_has_the_reason(db: str) -> None:
    def line(*args: str) -> dict[str, object]:
        out = CliRunner().invoke(cli, ["--db", db, "detect", "--json", *args])
        return json.loads(out.stdout.splitlines()[0])  # type: ignore[no-any-return]

    assert line("--id", "MIT")["reason"] is None
    assert line("--text", GIBBERISH)["reason"] == "no match"
    assert line("--threshold", "0.99", "--text", CLOSE)["reason"] == ("below threshold")
    assert line("--threshold", "0", "--exact", "--text", CLOSE)["reason"] == (
        "not exact"
    )
    assert line("--text", GIBBERISH)["expression"] is None
