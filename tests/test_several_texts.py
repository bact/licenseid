# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Made-up files of several licence texts (``several_texts``, built from the
long-text fixtures): a text answer stands only when its text comes first
(``licenseid.firsttext``), and a record of no answer names the texts found
(``TEXTS``, ``REASON=several texts``). On the long-text fixture database,
which holds the near neighbours of each text with their text."""
# pylint: disable=missing-function-docstring

import json
from typing import Any

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from long_text_db import DB_PATH, long_text_detector
from matcher_db import PROSE
from several_texts import Expected, several_text, several_text_cases

from licenseid.cli import cli
from licenseid.result import read_text_field

CASES = {case: (text, expected) for case, text, expected in several_text_cases()}


def _record(*args: str, text: str) -> tuple[int, dict[str, str]]:
    """The exit code and the fields of the first ``detect -v`` line."""
    long_text_detector()  # builds the shared database
    result = CliRunner().invoke(
        cli, ["--db", DB_PATH, "detect", *args, "-"], input=text
    )
    lines = result.stdout.splitlines()
    assert len(lines) >= 1, result.output
    fields = dict(field.split("=", 1) for field in lines[0].split("\t"))
    return result.exit_code, {k: read_text_field(v) for k, v in fields.items()}


def test_the_recipes_are_the_ten_cases() -> None:
    assert list(CASES) == [
        "apache-then-mit",
        "gpl3-then-mit",
        "mit-then-gpl3",
        "mit-then-apache",
        "numpy-like",
        "cpython-like",
        "or-file",
        "own-not-found",
        "one-text",
        "mpl-header-notice",
    ]
    assert all(len(case) <= 20 for case in CASES)  # short test IDs (Windows)


@pytest.mark.parametrize("case", list(CASES))
def test_detect_answers_only_when_the_answers_text_is_first(
    case: str, given: GivenWarnings
) -> None:
    text, expected = CASES[case]
    detector = long_text_detector()
    results = detector.detect(text=text)
    if expected.answer is None:
        if expected.reason == "several texts":  # the rule leaves no result
            assert not results, results[0]["expression"]
        else:
            assert results[0]["score"] < 0.85
        assert detector.texts(text) == (list(expected.texts) or None)
        return
    assert results[0]["expression"] == expected.answer
    assert results[0]["score"] >= 0.85
    assert results[0]["texts"] == list(expected.texts)
    # GPL-3.0's text states no variant: -only is a guess, said once.
    assert given.conditions() <= {"variant not stated"}


@pytest.mark.parametrize("case", list(CASES))
def test_the_record_names_the_texts_and_the_reason(case: str) -> None:
    text, expected = CASES[case]
    code, fields = _record("-v", text=text)
    _check_record(code, fields, expected)


def _check_record(code: int, fields: dict[str, Any], expected: Expected) -> None:
    assert code == (1 if expected.answer is None else 0)
    assert (fields["EXPRESSION"] or None) == expected.answer
    assert (fields["REASON"] or None) == expected.reason
    assert fields["TEXTS"] == " ".join(expected.texts)


@pytest.mark.terse_cli
@pytest.mark.parametrize("case", ["mit-then-gpl3", "gpl3-then-mit"])
def test_every_output_gives_one_answer(case: str, given: GivenWarnings) -> None:
    """The search runs where ``TEXTS`` is never printed too (the ``skipped``
    trap of item 67): terse ``detect``, ``--json``, ``is-osi`` and
    ``is_osi()`` agree with ``-v``."""
    text, expected = CASES[case]
    answer = expected.answer
    long_text_detector()  # builds the shared database
    runner = CliRunner()
    terse = runner.invoke(cli, ["--db", DB_PATH, "detect", "-"], input=text)
    assert terse.stdout.splitlines()[0] == (answer or "")
    as_json = runner.invoke(cli, ["--db", DB_PATH, "detect", "--json", "-"], input=text)
    record = json.loads(as_json.stdout.splitlines()[0])
    assert (record["expression"], record["reason"]) == (answer, expected.reason)
    assert record["texts"] == list(expected.texts)
    is_osi = runner.invoke(cli, ["--db", DB_PATH, "is-osi", "-"], input=text)
    assert is_osi.stdout.startswith(f"EXPRESSION={answer or ''}\t")
    flag = long_text_detector().is_osi(text=text)
    assert (flag is None) == (answer is None)
    assert given.conditions() <= {"variant not stated"}


def test_the_api_texts_function_names_each_group() -> None:
    """``LicenseDetector.texts``: the GPL-3.0 group by its ``-only`` form under
    ``auto`` and by its ``-or-later`` form under ``or-later``; under 40
    tokens, None."""
    detector = long_text_detector()
    text = several_text("mit-then-gpl3")
    assert detector.texts(text) == ["MIT", "GPL-3.0-only"]
    assert detector.texts(text, variant="or-later") == ["MIT", "GPL-3.0-or-later"]
    assert detector.texts(" ".join(text.split()[:20])) is None
    assert detector.texts("") is None


def test_mypy_extensions_shape_answers_its_text() -> None:
    """mypy_extensions' shape: a line naming the licence, ``= = = = =``, then
    the MIT text. Its top was a look-alike under 0.85 (OSSP, 0.70) while the
    FTS5 query of 0.9 missed MIT; the word grams find it (roadmap item 68)."""
    text = (
        "Example Project is licensed under the terms of the MIT license,"
        " reproduced below.\n\n= = = = =\n\n" + several_text("one-text")
    )
    code, fields = _record("-v", text=text)
    assert code == 0
    assert (fields["EXPRESSION"], fields["REASON"], fields["TEXTS"]) == (
        "MIT",
        "",
        "MIT",
    )


def test_a_record_below_the_threshold_names_the_text_it_holds() -> None:
    """Prose three times as long as the MIT text, then the text: the top is
    MIT at about 0.72, so no answer; the record still names the MIT text the
    file holds (0.9.3 left it empty)."""
    text = PROSE * 4 + "\n\n" + several_text("one-text")
    code, fields = _record("-v", text=text)
    assert code == 1
    assert (fields["EXPRESSION"], fields["REASON"], fields["TEXTS"]) == (
        "",
        "below threshold",
        "MIT",
    )
    as_json = CliRunner().invoke(
        cli, ["--db", DB_PATH, "detect", "--json", "-"], input=text
    )
    assert json.loads(as_json.stdout)["texts"] == ["MIT"]
