# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden ``detect()`` answers moved by ``resolve()`` reading the other
names a BSD licence is known by (``licenseid.resolvealias``), for
``harness_changes.DETECT_CHANGES``: ``{case: (new value, reason)}``. Most
were lost by PR #161 or #168 (no answer, listed in their tables); merged
last, this table gives each its answer now."""

_THREE = "BSD-3-Clause\tname\tyes\t1.0000"
_TWO = "BSD-2-Clause\tname\tyes\t1.0000"
_ALIAS = "resolve() reads the BSD alias (alias_name): exact, by name"
_INEXACT = "resolve() reads the BSD alias (alias_name): exact now (was a name guess)"

_CASES: dict[str, tuple[str, str]] = {
    "value/2-clause BSD": (_TWO, _ALIAS),
    "value/2-clause BSD License": (_TWO, _ALIAS),
    "value/3-Clause BSD License": (_THREE, _ALIAS),
    "value/3-clause BSD": (_THREE, _ALIAS),
    "value/BSD 3": (_THREE, _ALIAS),
    "value/BSD-3": (_THREE, _ALIAS),
    "value/BSD3": (_THREE, _ALIAS),  # no answer in the golden
    "value/Modified BSD License": (_THREE, _ALIAS),
    "value/New BSD": (_THREE, _ALIAS),
    "value/New BSD License": (_THREE, _ALIAS),
    "value/New BSD license": (_THREE, _ALIAS),
    "value/Revised BSD License": (_THREE, _ALIAS),
    "value/Simplified BSD": (_TWO, _ALIAS),
    "value/Simplified BSD license": (_TWO, _INEXACT),
    "value/Two-clause BSD license": (_TWO, _ALIAS),
    "value/modified BSD": (_THREE, _ALIAS),
    "value/new BSD": (_THREE, _ALIAS),
}

ALIAS_CHANGES: dict[str, tuple[str, str]] = _CASES
