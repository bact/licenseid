# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden values the first-text rule moves (roadmap item 59,
``licenseid.firsttext``): in a file of several licence texts a text answer
stands only when its text comes first, and ``TEXTS`` follows the order of
the file. Merged last into
``harness_changes.DETECT_CHANGES`` and ``CLI_CHANGES``."""

_SEVERAL = "several licence texts; the answer's text is not first: no answer"
_NONE = "-\t-\t-\t-"

FIRSTTEXT_CHANGES: dict[str, tuple[str, str]] = {
    "several/mit-then-gpl3": (_NONE, _SEVERAL),
    "several/mit-then-apache": (_NONE, _SEVERAL + " (pytype's shape: a known loss)"),
    "several/numpy-like": (_NONE, _SEVERAL),
    "several/or-file": (_NONE, _SEVERAL + " (either text, at the user's option)"),
    "several/own-not-found": (
        _NONE,
        _SEVERAL + "; the top was a look-alike under the threshold",
    ),
}
FIRSTTEXT_CLI_CHANGES: dict[str, tuple[str, str]] = {
    "detect-several-texts#text": (
        "4febc2c8c291",
        _SEVERAL + "; REASON=several texts, TEXTS names both in file order",
    ),
    "detect-several-texts#json": (
        "98f7eaf4ab5b",
        _SEVERAL + "; reason several texts, texts names both in file order",
    ),
}
