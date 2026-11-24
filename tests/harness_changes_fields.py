# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The CLI golden digests moved by the record fields added after
``VARIANT_STATED``, for ``harness_changes.CLI_CHANGES`` (``{case#mode: (digest,
reason)}``). Loaded after ``harness_changes_variant``: a case both move has the
digest of this file. One reason constant per field; each digest is that of
the record with every field."""

from harness_changes_variant import VARIANT_CLI_CHANGES

_SAME_TEXT = (
    "the record has a field SAME_TEXT after VARIANT_STATED (JSON same_text):"
    " empty unless a text answer shares its text with other List IDs"
)

_REASON = (
    "the record has a field REASON after SAME_TEXT (JSON reason): empty on an"
    " answer, on no answer one of below threshold, not exact, no match"
)

# The digests, in the order of the sorted case keys (the cases of
# ``harness_changes_variant`` too: the same ones are moved).
_DIGESTS = (
    "089c2b40a243",
    "bd8a47474e1e",
    "6abc32df49a0",
    "1b547e0fd720",
    "6ce529873530",
    "77abec61824f",
    "c41e526704e2",
    "03b16afb761b",
    "5b8553a4a998",
    "36bc12aea406",
    "b3300b30613a",
    "5f22a20e8e73",
    "16f36d760d4d",
    "1cc3d3e3ee30",
    "1748cf8140ca",
    "b4e7237bef22",
    "2e2e4248c0d9",
    "c4fbc53b578d",
    "3db9dbe0559a",
    "4ab2807d83cb",
    "5774caf1d8a6",
    "cb8fe0e05046",
    "333b84c24589",
    "e30d5dd0db5b",
    "86121a646f82",
    "7cb9bdffaab0",
    "d40aad1859b2",
    "02ea381cb037",
    "540dd8d39848",
)

FIELDS_CHANGES: dict[str, tuple[str, str]] = {
    key: (digest, _SAME_TEXT + "; " + _REASON)
    for key, digest in zip(sorted(VARIANT_CLI_CHANGES), _DIGESTS)
}
