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
    "no text match after a dropped mark or an unpaired bracket, "
    "so too few words for text"
)

_PARTIAL = (
    "the long-text fixture database holds no row for the deprecated ID, which "
    "resolve() needs and the full List has (a harness artefact, not a loss)"
)

WRAPPER_CHANGES: dict[str, tuple[str, str]] = {
    "value/#MIT": (_NONE, _DROPPED),
    "value/Apache 2.0?": (_NONE, _DROPPED),
    "value/MIT�": (_NONE, _DROPPED),
    "value/(MIT": (_NONE, _DROPPED),  # an unbalanced bracket
    "value/Apache 2.0!": (_NONE, _DROPPED),
    "value/MIT*": (_NONE, _DROPPED),
    "value/MIT\x00": (_NONE, _DROPPED),
    "value/\u202eMIT": (_NONE, _DROPPED),
    "id/GPL-2.0-only/id_deprecated": (_NONE, _PARTIAL),
    "id/GPL-2.0-or-later/id_deprecated": (_NONE, _PARTIAL),
    "id/LGPL-2.0-or-later/id_deprecated": (_NONE, _PARTIAL),
    "id/LGPL-3.0-only/id_deprecated": (_NONE, _PARTIAL),
    "id/AGPL-1.0-only/id_deprecated": (_NONE, _PARTIAL),
    "id/GPL-3.0-or-later/id_deprecated": (_NONE, _PARTIAL),
}
