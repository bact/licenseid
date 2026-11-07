# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The changes the golden snapshots of the pre-release harness accept, as
``resolver_corpus.EXPECTED_CHANGES`` does for the resolver: a pull request
that moves a golden value lists it here with the new value and the reason,
and no other value may move. Regenerate the golden file once the release is
frozen (``python -m tools.golden --write``) and empty these tables.

``DETECT_CHANGES``: ``{"kind/case": ("expression\\tmethod\\texact\\tscore",
reason)}`` for the ``detect()`` golden. ``CLI_CHANGES``:
``{"case#mode": (digest, reason)}``, the digest from ``tools.golden``
(``python -m tools.golden`` prints it)."""

from harness_changes_aliases import ALIAS_CHANGES
from harness_changes_nametier import NAME_TIER_CHANGES
from harness_changes_resolvefirst import RESOLVE_FIRST_CHANGES
from harness_changes_versioned import VERSIONED_CHANGES

_FIRST = "resolve() reads the whole value: Apache-2.0 alone, nothing measured"
_SHORT = "still no answer, now with resolve()'s reason: input: too few words for text"

DETECT_CHANGES: dict[str, tuple[str, str]] = {
    **RESOLVE_FIRST_CHANGES,
    **NAME_TIER_CHANGES,
    **ALIAS_CHANGES,  # last: a value it moves again has its answer now
    **VERSIONED_CHANGES,
}
CLI_CHANGES: dict[str, tuple[str, str]] = {
    "detect-name#text": ("bea927311e33", _FIRST),
    "detect-name#json": ("486cff182afc", _FIRST),
    "detect-text-no-answer#text": ("e22d744658d1", _SHORT),
    "detect-text-no-answer#json": ("0f14c7433df9", _SHORT),
    "detect-unreadable-text#text": ("0df77ec6c59b", _SHORT),
    "detect-unreadable-text#json": ("13301d901e3b", _SHORT),
}
