# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``EXACT`` of a cut version with an "or later" grant, in every channel
(roadmap item 52, rule (a)).

``LGPLv2 or later`` is read by a rewrite rule (``version_spelling``: a cut
version, covered by its grant), so it is ``EXACT=false`` as the argument. A
tag or a field judged the ID before the grant alone, which ``resolve()``
refuses since item 54 (``version ambiguous``), so no rule "read" it and it
was exact. The tag judges the expression with its grant now
(``ruleread.tag_inexact``), after a WITH and inside a compound too.
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import answers

from licenseid import LicenseDatabase

#: ``value: (expression, exact)`` in the argument, a tag and a field alike.
INEXACT = {
    "LGPLv2 or later": "LGPL-2.0-or-later",
    "LGPL-2 or later": "LGPL-2.0-or-later",
    "Apache-1 or later": "Apache-1.0+",
    "CDDL-1 or later": "CDDL-1.0+",
    "GPLv2 or later": "GPL-2.0-or-later",
    "GPLv2 WITH Classpath-exception-2.0 or later": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0"
    ),
    "LGPL-2 WITH Classpath-exception-2.0 or later": (
        "LGPL-2.0-or-later WITH Classpath-exception-2.0"
    ),
    "MIT OR LGPLv2 or later": "LGPL-2.0-or-later OR MIT",
    "LGPLv2+": "LGPL-2.0-or-later",
    "Apache-1+": "Apache-1.0+",
}

#: Written whole: exact in every channel.
EXACT = {
    "GPL-2.0 or later": "GPL-2.0-or-later",
    "MIT or later": "MIT+",
    "LGPL-2.1 or later": "LGPL-2.1-or-later",
    "GPL-2.0 WITH Classpath-exception-2.0 or later": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0"
    ),
    "GPL-2.0+": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", sorted(INEXACT), ids=lambda v: v[:40])
def test_a_cut_version_with_a_grant_is_not_exact(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = answers(corpus_db, value)
    assert got == dict.fromkeys(("argument", "tag", "field"), (INEXACT[value], False))


@pytest.mark.parametrize("value", sorted(EXACT), ids=lambda v: v[:40])
def test_a_grant_written_whole_is_exact(corpus_db: LicenseDatabase, value: str) -> None:
    got = answers(corpus_db, value)
    assert got["tag"] == (EXACT[value], True)
    assert got["field"] == (EXACT[value], True)


def test_a_comma_before_a_grant_keeps_a_tag_exact(corpus_db: LicenseDatabase) -> None:
    """The comma is a separator the argument records (``EXACT=false``); a tag
    ends its expression at the grant and judges ``GPL-2.0-or-later``."""
    got = answers(corpus_db, "GPL-2.0, or later")
    assert got["argument"] == ("GPL-2.0-or-later", False)
    assert got["tag"] == ("GPL-2.0-or-later", True)
