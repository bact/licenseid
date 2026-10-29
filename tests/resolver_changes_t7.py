# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers task T7 (compound expressions) moved in the parity corpus
and the PyPI sample, grouped by the decision that moved them.

``resolver_corpus.EXPECTED_CHANGES`` merges :data:`T7_CHANGES`. Each group
is a table ``{value: answer}`` and one reason; :func:`answer` builds an
answer by keyword, its defaults the answer that resolves nothing.
"""

from tools.pypi_licence_sample.answer import Answer


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


_Q20 = (
    "T7 (Q20): an AdditionRef- exception is accepted as a LicenseRef- is,"
    " unchecked against the list; 0.6.0 refused it"
)

_ADDITION_REF = {
    "MIT WITH AdditionRef-x": answer(
        "MIT WITH AdditionRef-x", "exact", trust="identity"
    ),
}

#: ``{value: (answer, reason)}``, every group of T7.
T7_CHANGES: dict[str, tuple[Answer, str]] = {
    value: (got, why)
    for table, why in ((_ADDITION_REF, _Q20),)
    for value, got in table.items()
}
