# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden answers that moved when Tier 0 stopped reading a value
``resolve()`` refuses as an ID (roadmap item 48): a short value that
``resolve()`` refuses for a dropped mark gets no ID and no name answer, as
a "+" that is no operator did since item 44."""

_NONE = "-\t-\t-\t-"
_DROPPED = (
    "resolve() refuses it for a mark it would drop (character dropped): "
    "no ID read from the normalised text, so too few words for text"
)

WRAPPER_CHANGES: dict[str, tuple[str, str]] = {
    "id/CC-BY-NC-SA-2.0-DE/id_punct": (_NONE, _DROPPED),
    "id/OSL-3.0/id_punct": (_NONE, _DROPPED),
    "value/#MIT": (_NONE, _DROPPED),
    "value/Apache 2.0?": (_NONE, _DROPPED),
    "value/MIT�": (_NONE, _DROPPED),
}
