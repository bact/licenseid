# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and the prose forms of one licence ID (task T8, rules P1 to
P3). Characterisation: what the resolver answered before the rules, so that
the change shows as a flip of the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: Values T8 reads; the answer before it is "unresolved".
MOVES = {
    "Apache-2.0 license": "Apache-2.0",
    "BSD 3-Clause License": "BSD-3-Clause",
    "MIT Licence": "MIT",
    "The MIT License": "MIT",
    "The BSD 2-Clause License": "BSD-2-Clause",
    "Apache License, Version 2.0": "Apache-2.0",
    "Apache License v2.0": "Apache-2.0",
}
#: Values T8 leaves as they are.
STAYS = [
    "BSD License",
    "Apache Software License",
    "W3C license",
    "Apache License, Version 3.0",
    "GNU General Public License v3",
    "Dual License",
    "The MIT",
]


@pytest.mark.parametrize("value", sorted(MOVES), ids=lambda v: v[:24])
def test_before_the_rules_a_prose_form_is_unresolved(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] is None  # MOVES


@pytest.mark.parametrize("value", STAYS, ids=lambda v: v[:24])
def test_a_near_miss_is_unresolved(corpus_db: LicenseDatabase, value: str) -> None:
    assert resolve(value, corpus_db)["expression"] is None
