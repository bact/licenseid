# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The "+" operator of an SPDX expression: the one reader of it.

Standard library only, so every module that reads an ID can import it.
"""

import re

# The "+" ("or any later version") operator, which py_spdx_license cannot
# parse (https://github.com/JPEWdev/py-spdx-license/issues/1): it only ever
# follows the last character of a license ID, so a "+" after a space, a "(" or
# another "+", after the exception of a WITH, or after an operator word
# (WITH, AND, OR), is not one. The ID must start at a token start (lookbehind):
# without it every offset of a long token is tried and the scan is quadratic
# (8 s at 32,000 characters).
PLUS_OPERATOR = re.compile(
    r"(?P<with>\bWITH\s+)?(?<![^\s(])(?!(?:with|and|or)\+)"
    r"(?P<id>[^\s()+]+)\+(?=\s|\)|$)",
    re.IGNORECASE,
)
# A license reference: SPDX gives "+" to a license ID only
# (simple-expression = license-id / license-id "+" / license-ref).
LICENSE_REF_PREFIX = re.compile(
    r"(?:DocumentRef-[^\s():]+:)?LicenseRef-", re.IGNORECASE
)


def plus_after_qualifier(expression: str) -> bool:
    """Whether a "+" operator in *expression* follows an ID that states its
    qualifier already ("GPL-2.0-only+", "GPL-2.0-or-later+"): no SPDX ID
    takes both, so the value names no license."""
    return any(
        match.group("id").lower().endswith(("-only", "-or-later"))
        for match in PLUS_OPERATOR.finditer(expression)
        if not match.group("with") and not LICENSE_REF_PREFIX.match(match.group("id"))
    )


def strip_plus_operator(expression: str) -> str:
    """Drop the "+" operators of *expression* so ``py_spdx_license`` can parse
    it (``Apache-2.0+ OR MIT`` becomes ``Apache-2.0 OR MIT``). A "+" that is
    not an operator stays, so the expression stays unparseable."""
    return replace_plus_operator(expression, "")


def replace_plus_operator(text: str, replacement: str) -> str:
    """*text* with each "+" operator after a license ID replaced by
    *replacement*: "" drops it, " or later" spells it out
    (``versionkey.version_key``). Any other "+" stays."""

    def replace(match: re.Match[str]) -> str:
        # Neither an exception nor a LicenseRef takes a "+".
        if match.group("with") or LICENSE_REF_PREFIX.match(match.group("id")):
            return match.group(0)
        return match.group("id") + replacement

    return PLUS_OPERATOR.sub(replace, text)
