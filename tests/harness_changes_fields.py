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

_TEXTS = (
    "the record has a field TEXTS after REASON (JSON texts): empty unless a text"
    " answer is exact or its input of 40 tokens or more holds List texts whole"
)

# The digests, in the order of the sorted case keys (the cases of
# ``harness_changes_variant`` too: the same ones are moved).
_DIGESTS = (
    "5439c27e0089",
    "7d5765ca6d65",
    "3fb691dfad69",
    "7fa149ed6f04",
    "f62a8eed978a",
    "b460cc6af2ac",
    "94218943a255",
    "c79d328bc9b2",
    "5334b8784e2b",
    "581f712a2bdc",
    "2ae4640c06f1",
    "ce328645b4f8",
    "cf9f68f0c7f4",
    "67a7c8b39d0e",
    "700597c646e0",
    "2e32aaf7e09f",
    "11a44367610c",
    "a4fd938d753b",
    "9df6458baafb",
    "eca0e679d092",
    "ba682c07b2e1",
    "2b14e93c140a",
    "1f210eca7d4a",
    "fc5e9b27016b",
    "0e3356427d0b",
    "a466d101cb63",
    "1f7d24fc2e13",
    "3ddc84309b2a",
    "1dcd852431ec",
)

FIELDS_CHANGES: dict[str, tuple[str, str]] = {
    key: (digest, _SAME_TEXT + "; " + _REASON + "; " + _TEXTS)
    for key, digest in zip(sorted(VARIANT_CLI_CHANGES), _DIGESTS)
}
