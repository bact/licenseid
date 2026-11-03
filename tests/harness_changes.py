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

DETECT_CHANGES: dict[str, tuple[str, str]] = {}
CLI_CHANGES: dict[str, tuple[str, str]] = {}
