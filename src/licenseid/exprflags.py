# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What SPDX, the OSI and the FSF say of a parsed licence expression.

The OSI and FSF flags of a compound are evaluated from its operands: an
``AND`` holds when every operand does, an ``OR`` when any does, and a
``WITH`` takes the flag of its licence (an exception is approved by
neither). An operand that cannot be judged (an ID not on the list, a
``LicenseRef-*``) is None, and the logic has three values: an ``OR`` with a
true operand is true and an ``AND`` with a false one is false, whatever the
others are; otherwise one None makes the whole None. So a compound is never
answered "no" for a licence nobody judged, and one judged operand that
decides it is enough. ``is_spdx`` holds only when every licence and
exception ID is on the SPDX License List: a ``LicenseRef-*`` is a valid
SPDX expression, but not on the List.

A bare deprecated ID that is kept as written (``GPL-2.0``) and a deprecated
``-with-`` ID (``GPL-2.0-with-classpath-exception``) are judged by the ``-only``
twin (the ``-with-`` ID by ``<bare>-only``, as ``<bare>-only WITH <exception>``
is), not by their own List rows: the two twins have equal flags (a test pins
it), and a bare row can differ (``AGPL-1.0`` is FSF-libre; its twins are not;
the ``GPL-2.0-with-*`` rows are neither OSI nor FSF).
"""

from typing import TYPE_CHECKING, Final

import py_spdx_license

from licenseid.deprecatedids import DEPRECATED_BARE_LICENSE_IDS, DEPRECATED_WITH_IDS
from licenseid.exprtokens import without_addition_refs
from licenseid.identifiers import parse_declared
from licenseid.listlookup import fold_case
from licenseid.types import LicenseDetails, LicenseFlags

if TYPE_CHECKING:
    from licenseid.database import LicenseDatabase

#: A kept deprecated ID (case-folded) to the ``-only`` ID that is judged for it.
_TWIN_OF: Final[dict[str, str]] = {
    **{fold_case(k): v for k, v in DEPRECATED_BARE_LICENSE_IDS.items()},
    **{
        fold_case(k): v.split(" WITH ", maxsplit=1)[0]
        for k, v in DEPRECATED_WITH_IDS.items()
    },
}

# The two flags an operand carries, (OSI, FSF); None: cannot be judged.
Flags = tuple[bool | None, bool | None]
_UNJUDGED: Flags = (None, None)


def declared_flags(value: str, db: "LicenseDatabase") -> LicenseFlags | None:
    """The flags of *value*, an ID that is not in *db* or an expression, or
    None when it is no evidence of a licence.

    Keeps only well-formed SPDX expressions and ``LicenseRef-*`` IDs with at
    least one recognised ID: fabricating a candidate from arbitrary text
    ("see LICENSE file", "Dual OR Commercial") would create a phantom
    licence ranked at a fixed high confidence.
    """
    tree = parse_declared(value)
    if tree is None:
        return None  # not an expression (or too deep to parse)
    known = (py_spdx_license.LicenseId, py_spdx_license.LicenseRef)
    if not any(isinstance(leaf, known) for leaf in _leaves(tree)):
        return None
    return expression_flags(tree, db)


def judged_flags(value: str, db: "LicenseDatabase") -> LicenseFlags | None:
    """:func:`declared_flags` of *value*, a ``WITH AdditionRef-*`` read as
    its licence (a ``WITH`` takes its licence's flags): ``MIT WITH
    AdditionRef-x OR ISC`` is OSI-approved. An ``AdditionRef-*`` is not on
    the List, so such a value is not ``is_spdx``."""
    stripped, dropped = without_addition_refs(value)
    flags = declared_flags(stripped, db)
    if flags is not None and dropped:
        flags["is_spdx"] = False
    return flags


def _leaves(node: py_spdx_license.Node) -> list[py_spdx_license.Node]:
    """The identifier nodes of a parsed expression."""
    if isinstance(node, py_spdx_license.Identifier):
        return [node]
    return [leaf for child in node.children for leaf in _leaves(child)]


def expression_flags(tree: py_spdx_license.Node, db: "LicenseDatabase") -> LicenseFlags:
    """The flags of the expression *tree*, read from the rows of *db*."""
    osi, fsf = _flags(tree, db)
    return {
        "is_spdx": _on_the_list(tree, db),
        "is_osi_approved": osi,
        "is_fsf_libre": fsf,
    }


def _flags(node: py_spdx_license.Node, db: "LicenseDatabase") -> Flags:
    """The (OSI, FSF) flags of *node*: its row's for a licence ID, its
    licence's for a ``WITH``, all or any of its operands' for an ``AND`` or
    an ``OR``. The parser's depth cap bounds the recursion."""
    if isinstance(node, py_spdx_license.WithOp):
        return _flags(node.license, db)
    if isinstance(node, (py_spdx_license.AndOp, py_spdx_license.OrOp)):
        operands = [_flags(child, db) for child in node.children]
        # AND is decided by a False, OR by a True.
        decisive = not isinstance(node, py_spdx_license.AndOp)
        return (
            _combined([osi for osi, _ in operands], decisive),
            _combined([fsf for _, fsf in operands], decisive),
        )
    if isinstance(node, py_spdx_license.LicenseRef):
        return _UNJUDGED
    if isinstance(node, py_spdx_license.Identifier):
        row = db.get_license_details(judged_id(node.ident))
        if row is None:
            return _UNJUDGED
        return bool(row["is_osi_approved"]), bool(row["is_fsf_libre"])
    return _UNJUDGED


def judged_id(ident: str) -> str:
    """The ID whose row says what the OSI and FSF think of *ident*: the
    ``-only`` twin of a bare or ``-with-`` deprecated ID, else *ident*."""
    return _TWIN_OF.get(fold_case(ident), ident)


def judged_details(db: "LicenseDatabase", lic_id: str) -> LicenseDetails | None:
    """The row of *lic_id*, flagged as :func:`with_judged_flags`, or None."""
    details = db.get_license_details(lic_id)
    return with_judged_flags(details, db) if details else None


def with_judged_flags(details: LicenseDetails, db: "LicenseDatabase") -> LicenseDetails:
    """*details* with the OSI and FSF flags of :func:`judged_id`; the row
    itself when its ID has no twin or the twin has no row."""
    twin = judged_id(details["license_id"])
    row = db.get_license_details(twin) if twin != details["license_id"] else None
    if row is None:
        return details
    return {
        **details,
        "is_osi_approved": row["is_osi_approved"],
        "is_fsf_libre": row["is_fsf_libre"],
    }


def _combined(values: list[bool | None], decisive: bool) -> bool | None:
    """*values* joined in three-valued logic: *decisive* (True for an OR,
    False for an AND) if one of them is, else None if one is None, else the
    other truth value."""
    if decisive in values:
        return decisive
    if None in values:
        return None
    return not decisive


def _on_the_list(node: py_spdx_license.Node, db: "LicenseDatabase") -> bool:
    """Whether every licence and exception ID of *node* is on the List."""
    if isinstance(node, py_spdx_license.LicenseRef):
        return False
    if isinstance(node, py_spdx_license.ExceptionId):
        return db.get_exception_details(node.ident) is not None
    if isinstance(node, py_spdx_license.Identifier):
        return db.get_license_details(node.ident) is not None
    return all(_on_the_list(child, db) for child in node.children)
