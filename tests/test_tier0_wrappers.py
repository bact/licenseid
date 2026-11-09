# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A short value ``resolve()`` refuses, and a quoted manifest field, on the
paths of ``detect()`` (tech-debt roadmap, item 48).

Tier 0 read the normalised text of such a value, so a wrapper and a "+" had
gone: ``「GPL-2.0+」`` was ``GPL-2.0-only``, ``「MIT++」`` was ``MIT``, and a
quoted INI ``GPL-2.0+`` lost its operator. A value ``resolve()`` reads is the
answer of ``detect()`` whatever brings it; one it refuses is matched by name
only. A database of the whole List (``corpus_db``)."""
# pylint: disable=missing-function-docstring

import warnings
from collections.abc import Callable
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.types import Detection

Answer = tuple[str, str, bool] | None


def _top(found: list[Detection]) -> Answer:
    if not found:
        return None
    return (found[0]["expression"], found[0]["method"], found[0]["exact"])


def _whole(_: Path, value: str) -> str:
    return value


def _ini(_: Path, value: str) -> str:
    return f'[metadata]\nlicense = "{value}"\n'


def _ini_file(_: Path, value: str) -> str:
    return _ini(_, value)


MAKE: dict[str, Callable[[Path, str], str]] = {
    "whole": _whole,
    "ini": _ini,
    "ini file": _ini_file,
}


def _detect(detector: LicenseDetector, tmp: Path, route: str, value: str) -> Answer:
    text = MAKE[route](tmp, value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if route == "ini file":  # the CLI's file with no extension
            path = tmp / "manifest"
            path.write_text(text, encoding="utf-8")
            return _top(detector.detect(file_path=str(path)))
        return _top(detector.detect(text=text))


# (value, route, answer). The rows of item 48: each was a wrong answer.
OR_LATER: Answer = ("GPL-2.0-or-later", "id", True)
PINS: list[tuple[str, str, Answer]] = [
    ("「GPL-2.0+」", "whole", OR_LATER),  # was GPL-2.0-only: the "+" lost
    ("<GPL-2.0+>", "whole", None),
    ("「GPL-2.0-only+」", "whole", None),  # was GPL-2.0-only, exact
    ("「MIT++」", "whole", None),  # was MIT, exact
    ("<MIT>", "whole", None),  # resolve() refuses: character dropped
    ("*MIT*", "whole", None),
    ("MIT*", "whole", None),
    ("「MIT」", "whole", ("MIT", "id", True)),  # read as quotes
    ("『MIT OR ISC』", "whole", ("ISC OR MIT", "id", True)),
    ("BSD (3 clause)", "whole", ("BSD-3-Clause", "name", True)),
    ("GPL-2.0+", "ini", ("GPL-2.0-or-later", "field", True)),  # was -only
    ("GPL-2+", "ini", ("GPL-2.0-or-later", "field", True)),
    ("AGPLv3+", "ini", ("AGPL-3.0-or-later", "field", True)),
    ("GPL-2.0+", "ini file", ("GPL-2.0-or-later", "field", True)),
    ("MIT OR ISC", "ini", ("ISC OR MIT", "field", True)),  # was no answer
    ("Apache 2.0 License", "ini", ("Apache-2.0", "field", True)),
    ("MIT++", "ini", None),
    ("「MIT++」", "ini", None),
]


@pytest.mark.parametrize(("value", "route", "expected"), PINS)
def test_pins(
    corpus_db: LicenseDatabase,
    tmp_path: Path,
    value: str,
    route: str,
    expected: Answer,
) -> None:
    detector = LicenseDetector(corpus_db.location)
    assert _detect(detector, tmp_path, route, value) == expected


# A value that stays refused, or must not change.
ADVERSARIAL = [
    "「MIT」x",
    "「MIT",
    "MIT」",
    "「MIT」」",
    "<<MIT>>",
    "**MIT**",
    "<GPL-2.0>+",
    "「MIT」 +",
    "MIT (C++)",
    "C++ MIT",
    "(MIT",  # resolve() refuses an unbalanced bracket; no ID from the text
    "MIT)",
]


@pytest.mark.parametrize("value", ADVERSARIAL)
def test_a_wrapper_or_plus_resolve_refuses_answers_no_licence(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    assert _detect(detector, tmp_path, "whole", value) is None
    assert _detect(detector, tmp_path, "ini", value) is None


def test_a_name_resolve_refuses_is_still_matched_by_name(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    """Names are Tier 0's own: only the ID readers went."""
    detector = LicenseDetector(corpus_db.location)
    found = _detect(detector, tmp_path, "whole", "Licensed under the MIT License")
    assert found is not None
    assert found[0] == "MIT"


@pytest.mark.parametrize("route", sorted(MAKE))
@pytest.mark.parametrize("value", ["MIT", "GPL-2.0+", "Apache-2.0", "MIT OR ISC"])
def test_a_value_resolve_reads_gives_one_expression_by_every_route(
    corpus_db: LicenseDatabase, tmp_path: Path, route: str, value: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    found = _detect(detector, tmp_path, route, value)
    assert found is not None
    assert found[0] == resolve(value, corpus_db)["expression"]
