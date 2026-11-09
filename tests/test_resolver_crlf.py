# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A declared value with Windows line ends (``\\r\\n``, a lone ``\\r``) reads as
the same value with ``\\n`` or none, in ``resolve()`` and in the files and
tags that reach it.

Every input here is written with explicit ``\\r``, so the test needs no
Windows: ``Path.write_text`` writes ``\\r\\n`` there only. A file is read as
bytes and its line ends become ``\\n`` at once
(``textinput.normalize_newlines``); a value given to ``resolve()`` or
``detect(text=...)`` is read as it is.
"""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.textinput import read_text_file

#: What a value ends or starts with when a Windows editor saved it.
ENDS = ["\r\n", "\r", "\n", "\r\n\r\n", " \r\n", "\t\r\n"]


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


#: Declared values that must read the same with a line end around them.
VALUES = [
    "MIT",
    "Apache-2.0",
    "GPL-2.0-or-later",
    "GPL-2.0+",
    "MIT OR Apache-2.0",
    "(MIT OR Apache-2.0) AND BSD-3-Clause",
    "GPL-2.0-only WITH Classpath-exception-2.0",
    "MIT/Apache-2.0",
    "Apache 2.0",
    "BSD 3-Clause License",
    "https://opensource.org/licenses/MIT",
    "License :: OSI Approved :: MIT License",
]


@pytest.mark.parametrize("end", ENDS, ids=[repr(e) for e in ENDS])
@pytest.mark.parametrize("value", VALUES)
def test_a_line_end_after_a_value_changes_nothing(
    corpus_db: LicenseDatabase, value: str, end: str
) -> None:
    bare = resolve(value, corpus_db)
    assert bare["expression"] is not None
    got = resolve(value + end, corpus_db)
    assert got["expression"] == bare["expression"]
    # CRLF is the LF of the same place, step for step (it may cost trust:
    # a line end is a step of its own, as a trailing "\n" is).
    lf = resolve(value + _lf(end), corpus_db)
    assert (got["category"], got["trust"]) == (lf["category"], lf["trust"])


@pytest.mark.parametrize("end", ENDS, ids=[repr(e) for e in ENDS])
@pytest.mark.parametrize("value", VALUES)
def test_a_line_end_before_a_value_changes_nothing(
    corpus_db: LicenseDatabase, value: str, end: str
) -> None:
    got = resolve(end + value, corpus_db)
    assert got["expression"] == resolve(value, corpus_db)["expression"]


#: A line end inside a value is white space: CRLF reads as LF.
INSIDE = [
    "MIT\r\nOR\r\nApache-2.0",
    "MIT\rOR\rApache-2.0",
    "GPL-2.0-or-later\r\nor later",
    "Apache\r\nLicense\r\n2.0",
    "BSD\r\n3-Clause\r\nLicense",
]


@pytest.mark.parametrize("value", INSIDE, ids=[repr(v) for v in INSIDE])
def test_crlf_inside_a_value_reads_as_lf(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got, want = resolve(value, corpus_db), resolve(_lf(value), corpus_db)
    assert got["expression"] == want["expression"]
    assert got["category"] == want["category"]


#: A tag line of a source file, saved with Windows line ends.
TAGS = [
    ("// SPDX-License-Identifier: MIT\r\n// more\r\n", "MIT"),
    ("# SPDX-License-Identifier: Apache-2.0\r\n", "Apache-2.0"),
    ("/* SPDX-License-Identifier: GPL-2.0-or-later */\r\n", "GPL-2.0-or-later"),
    ("# SPDX-License-Identifier: MIT OR Apache-2.0\r\nimport os\r\n", None),
    ("SPDX-License-Identifier: MIT\r", "MIT"),
]


@pytest.mark.parametrize("text", [t for t, _ in TAGS], ids=repr)
def test_a_tag_line_with_crlf_reads_like_one_with_lf(
    corpus_db: LicenseDatabase, text: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    got = [(m["expression"], m["method"]) for m in detector.detect(text)]
    assert got == [(m["expression"], m["method"]) for m in detector.detect(_lf(text))]
    assert got  # the tag names a licence: the control of the comparison


@pytest.mark.parametrize(("text", "expected"), TAGS, ids=repr)
def test_a_file_with_crlf_reads_as_its_bytes_say(
    corpus_db: LicenseDatabase, tmp_path: Path, text: str, expected: str | None
) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(text.encode("utf-8"))  # bytes: the same on every system
    assert read_text_file(str(path)) == _lf(text)  # one line end, at reading
    found = LicenseDetector(corpus_db.location).detect(file_path=str(path))
    assert found
    if expected is not None:
        assert found[0]["expression"] == expected
