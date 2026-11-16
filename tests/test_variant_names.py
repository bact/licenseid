# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The List name of a deprecated ID (``GNU General Public License v2.0``) in a
field or a tag declares that ID: ``auto`` keeps it, ``only`` and ``or-later``
decide it, a guess that is said (roadmap item 52)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import warnings
from collections.abc import Generator

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.detector import LicenseDetector
from licenseid.types import Variant
from licenseid.warning import LicenseIdWarning

NAME = "GNU General Public License v2.0"


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    with_row = Lic(
        "GPL-2.0-with-classpath-exception",
        "GNU General Public License v2.0 w/Classpath exception",
        False,
        is_deprecated=True,
    )
    yield from seeded_db(
        "test_variant_names", (*GPL2_ROWS, with_row), ["Classpath-exception-2.0"]
    )


@pytest.mark.parametrize(
    ("variant", "expected", "guessed"),
    [
        ("auto", "GPL-2.0", False),  # a declaration of the ID, as written
        ("only", "GPL-2.0-only", True),
        ("or-later", "GPL-2.0-or-later", True),
        ("as-written", "GPL-2.0", False),
    ],
)
@pytest.mark.parametrize("how", ["field", "tag"])
def test_a_deprecated_name_is_decided_by_the_option_in_every_channel(
    db: str, how: str, variant: str, expected: str, guessed: bool
) -> None:
    text = {
        "field": json.dumps({"license": NAME}),
        "tag": f"# SPDX-License-Identifier: {NAME}\n",
    }[how]
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always", LicenseIdWarning)
        found = LicenseDetector(db).detect(
            text=text,
            variant=variant,  # type: ignore[arg-type]
        )
    assert [r["expression"] for r in found[:1]] == [expected]
    assert [r["variant_stated"] for r in found[:1]] == [False]
    assert found[0]["exact"] is not guessed
    assert len(given) == (1 if guessed else 0)


def test_a_with_id_a_text_names_keeps_its_exception(db: str) -> None:
    """The ``-with-`` row is no twin of the bare ``-only`` row: replacing it
    must not drop the exception (``variant`` decides it, ``auto`` keeps it)."""
    text = (
        "This file is part of foo. It is licensed under"
        " GPL-2.0-with-classpath-exception. See the file COPYING in the top"
        " directory for the full terms and conditions of the licence that applies."
    )
    guesses: list[tuple[Variant, str]] = [("only", "-only"), ("or-later", "-or-later")]
    for chosen, expected in guesses:
        with warnings.catch_warnings(record=True) as given:
            warnings.simplefilter("always", LicenseIdWarning)
            top = LicenseDetector(db).detect(text=text, variant=chosen)[0]
        # The guess is said for a WITH answer too, and it is no stated one.
        assert top["expression"].endswith(f"{expected} WITH Classpath-exception-2.0")
        assert (top["variant_stated"], len(given)) == (False, 1)
        # The family is named, not the whole WITH answer.
        assert "variant not stated: GPL-2.0;" in str(given[0].message)
    got = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        for variant in ("auto", "only", "or-later"):
            found = LicenseDetector(db).detect(
                text=text,
                variant=variant,
            )
            got[variant] = [r["expression"] for r in found[:1]]
    assert all("Classpath" in e or "classpath" in e for v in got.values() for e in v), (
        got
    )


@pytest.mark.parametrize("variant", ["auto", "only", "or-later"])
def test_a_manifest_name_only_the_name_tier_reads_has_evidence(
    db: str, variant: str
) -> None:
    """``Licence`` is no List spelling, so the name tier answers the field: its
    value says "or later", so it is stated, and the option does not decide."""
    text = json.dumps({"license": "GNU General Public Licence v2.0 or later"})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        found = LicenseDetector(db).detect(
            text=text,
            variant=variant,  # type: ignore[arg-type]
        )
    top = found[0]
    assert (top["expression"], top["method"], top["variant_stated"]) == (
        "GPL-2.0-or-later",
        "field",
        True,
    )


@pytest.mark.parametrize("variant", ["only", "or-later"])
def test_words_after_a_tags_exception_state_nothing(db: str, variant: str) -> None:
    """A tag is judged by the expression it starts with (and the word beside
    it): ``only`` after an exception is neither, so the option decides and
    says so, as the decision and the record agree."""
    tag = "# SPDX-License-Identifier: GPL-2.0 WITH Classpath-exception-2.0 only\n"
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always", LicenseIdWarning)
        found = LicenseDetector(db).detect(
            text=tag,
            variant=variant,  # type: ignore[arg-type]
        )
    top = found[0]
    assert variant in top["expression"].lower().replace("-or-later", "or-later")
    assert (top["variant_stated"], len(given)) == (False, 1)


@pytest.mark.parametrize(
    ("variant", "excluded"),
    [
        ("only", "GPL-2.0-only"),
        ("or-later", "GPL-2.0-only"),
        ("or-later", "GPL-2.0-or-later"),
    ],
)
def test_the_option_does_not_bring_back_an_excluded_id(
    db: str, variant: Variant, excluded: str
) -> None:
    """A bare ID of a name match is decided after ``exclude`` ran: the form it
    becomes is not an excluded one, nor a second copy of one already there."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        found = LicenseDetector(db).detect(
            text=NAME, exclude=[excluded], variant=variant
        )
    ids = [r["expression"] for r in found]
    assert excluded not in ids
    assert len(ids) == len(set(ids))
