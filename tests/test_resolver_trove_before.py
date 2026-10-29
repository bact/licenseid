# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Characterisation for task T9 (trove names and paths, rules T1 to T3):
what ``resolve()`` answers for them before the rules exist.

The next commit flips these pins and moves them to
``test_resolver_trove.py``. Until then: a classifier path is read by no
rule, a trove name only where the SPDX List already names the licence the
same way (``MIT License``), and a trailing parenthesis never.
"""

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.trovenames import TROVE_NAMES

#: Names the List's own names (or loose IDs) already read.
READ_TODAY = {
    "Attribution Assurance License": "AAL",
    "Intel Open Source License": "Intel",
    "MIT License": "MIT",
    "Motosoto License": "Motosoto",
    "Nethack General Public License": "NGPL",
    "Nokia Open Source License": "Nokia",
    "Open Group Test Suite License": "OGTSL",
    "PostgreSQL License": "PostgreSQL",
    "Ricoh Source Code Public License": "RSCPL",
    "Sleepycat License": "Sleepycat",
    "University of Illinois/NCSA Open Source License": "NCSA",
    "X.Net License": "Xnet",
}


def _path(name: str) -> str:
    prefix = "License :: OSI Approved :: " if TROVE_NAMES[name].osi else "License :: "
    return prefix + name


@pytest.mark.parametrize("name", sorted(TROVE_NAMES), ids=lambda name: name[:24])
def test_a_trove_name_is_read_only_as_a_listed_name(
    corpus_db: LicenseDatabase, name: str
) -> None:
    assert resolve(name, corpus_db)["expression"] == READ_TODAY.get(name)


@pytest.mark.parametrize("name", sorted(TROVE_NAMES), ids=lambda name: name[:24])
def test_a_classifier_path_is_read_by_no_rule(
    corpus_db: LicenseDatabase, name: str
) -> None:
    assert resolve(_path(name), corpus_db)["expression"] is None


@pytest.mark.parametrize(
    "value",
    ["MIT License (MIT)", "MIT (MIT)", "Apache-2.0 (Apache-2.0)", "ISC (ISC)"],
)
def test_an_agreeing_trailing_parenthesis_is_not_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] is None
