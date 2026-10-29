# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers task T7 (compound expressions) moved in the parity corpus
and the PyPI sample, grouped by the decision that moved them.

The answers are in ``fixtures/resolver_t7_changes.tsv``, one row a value
with its group; :data:`REASONS` says why each group moved.
``resolver_corpus.EXPECTED_CHANGES`` merges :data:`T7_CHANGES`.
:func:`answer` builds an answer by keyword, its defaults the answer that
resolves nothing.
"""

from pathlib import Path

from tools.pypi_licence_sample.answer import (
    ANSWER_COLUMNS,
    Answer,
    answer_from_row,
    unescape_field,
)

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_t7_changes.tsv"


def answer(  # pylint: disable=too-many-arguments
    expression: str | None = None,
    category: str = "unresolved",
    *,
    trust: str = "none",
    steps: tuple[str, ...] = (),
    step_targets: tuple[str, ...] = (),
    expansions: tuple[str, ...] = (),
    expansion_targets: tuple[str, ...] = (),
    candidates: tuple[str, ...] = (),
    reason: str | None = None,
) -> Answer:
    """An answer by keyword; the defaults are "nothing resolved"."""
    return Answer(
        expression=expression,
        category=category,
        candidates=candidates,
        steps=steps,
        step_targets=step_targets,
        expansions=expansions,
        expansion_targets=expansion_targets,
        trust=trust,
        input_same=True,
        reason=reason,
    )


_WAS = "0.6.0 answered `expression` with no expression"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "canonical": (f"T7 (D1): a compound already in canonical order is read; {_WAS}"),
    "canonicalised": (
        "T7 (D1, Q19, Q24): a compound is read and written in canonical"
        f" order, operators upper case, duplicates dropped (`lexical`); {_WAS}"
    ),
    "weakest": (
        "T7 (D1): a compound takes the category of its weakest operand, each"
        f" operand read as it is alone; {_WAS}"
    ),
    "operand": (
        "T7 (D1): all or nothing, an operand that names no licence leaves the"
        " compound unresolved (named in the reason when the operators are in"
        f" upper case); {_WAS}"
    ),
    "reason": (
        "T7 (D1, P13, Q15): refused as before; with the operators in upper"
        " case the reason names the first operand that resolves to nothing,"
        " or is no operand (a leaf of several words that resolves alone: R7, S1)"
    ),
    "grammar": (
        "T7 (Q4): every part names a licence but the expression does not"
        " parse: `malformed`, the parser's message the reason; 0.6.0 said"
        " `expression`"
    ),
    "mark": (
        "T7: unresolved as before; the reason names the mark used where an"
        " SPDX operator belongs (IDs joined by / | & ; or ,)"
    ),
    "brackets": (
        "T7 (Q21): square and curly brackets read as round ones; 0.6.0 left"
        " the value unresolved"
    ),
    "addition_ref": (
        "T7 (Q20): an AdditionRef- exception is accepted as a LicenseRef- is,"
        " unchecked against the list; 0.6.0 refused it"
    ),
}


def _changes() -> dict[str, tuple[Answer, str]]:
    """The rows of :data:`CHANGES_FILE`, each with its group's reason."""
    changes: dict[str, tuple[Answer, str]] = {}
    lines = CHANGES_FILE.read_text(encoding="utf-8").splitlines()
    rows = [line.split("\t") for line in lines if not line.startswith("#")]
    for value, group, *fields in rows[1:]:
        row = dict(zip(ANSWER_COLUMNS, fields, strict=True))
        changes[unescape_field(value)] = (answer_from_row(row), REASONS[group])
    return changes


#: ``{value: (answer, reason)}``, every value T7 moves.
T7_CHANGES: dict[str, tuple[Answer, str]] = _changes()
