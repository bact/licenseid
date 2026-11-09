# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The one answer the "/" rule (``licenseid.resolveslash``, roadmap item 43)
moved in the parity corpus and the PyPI sample. ``resolver_corpus`` merges
:data:`SLASH_CHANGES` into ``EXPECTED_CHANGES`` last, over the T7 row that
recorded ``MIT/Apache-2.0`` as refused."""

from tools.pypi_licence_sample.answer import Answer

_WHY = (
    "item 43: IDs spelt as listed and joined by a `/` are read as `OR`"
    " (`separator`, `resolver_rule`, detail `slash as OR`); it was refused"
    " (`not an SPDX operator: /`). No other value of the corpus moves"
)

_READ = Answer(
    "Apache-2.0 OR MIT", "separator", (), (), (), (), (), "resolver_rule", True, None
)

#: ``{value: (answer, reason)}``.
SLASH_CHANGES: dict[str, tuple[Answer, str]] = {
    "MIT/Apache-2.0": (
        _READ._replace(
            steps=("separator", "reorder"),
            step_targets=("MIT OR Apache-2.0", "Apache-2.0 OR MIT"),
        ),
        _WHY,
    ),
}
