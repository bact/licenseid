# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What SPDX, the OSI and the FSF say of a parsed licence expression.

The OSI and FSF flags of a compound are evaluated from its operands: an
``AND`` holds when every operand does, an ``OR`` when any does, and a
``WITH`` takes the flag of its licence (an exception is approved by
neither). A flag is None, "cannot be judged", when any operand cannot be
judged: an ID not on the list, a ``LicenseRef-*``. So a compound is never
answered "no" for a licence nobody judged (decision F1 of the contract
batch). ``is_spdx`` holds only when every licence and exception ID is on
the SPDX License List: a ``LicenseRef-*`` is a valid SPDX expression, but
not on the List (F2).
"""

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

import py_spdx_license

from licenseid.identifiers import parse_declared
from licenseid.types import LicenseFlags

if TYPE_CHECKING:
    from licenseid.database import LicenseDatabase

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
        combine = all if isinstance(node, py_spdx_license.AndOp) else any
        return (
            _combined([osi for osi, _ in operands], combine),
            _combined([fsf for _, fsf in operands], combine),
        )
    if isinstance(node, py_spdx_license.LicenseRef):
        return _UNJUDGED
    if isinstance(node, py_spdx_license.Identifier):
        row = db.get_license_details(node.ident)
        if row is None:
            return _UNJUDGED
        return bool(row["is_osi_approved"]), bool(row["is_fsf_libre"])
    return _UNJUDGED


def _combined(
    values: list[bool | None], combine: Callable[[Iterable[object]], bool]
) -> bool | None:
    """*values* joined by *combine*, or None if one of them is None."""
    if any(value is None for value in values):
        return None
    return combine(values)


def _on_the_list(node: py_spdx_license.Node, db: "LicenseDatabase") -> bool:
    """Whether every licence and exception ID of *node* is on the List."""
    if isinstance(node, py_spdx_license.LicenseRef):
        return False
    if isinstance(node, py_spdx_license.ExceptionId):
        return db.get_exception_details(node.ident) is not None
    if isinstance(node, py_spdx_license.Identifier):
        return db.get_license_details(node.ident) is not None
    return all(_on_the_list(child, db) for child in node.children)
