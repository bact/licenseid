# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden detect() answers a cut ID no longer gets (roadmap item 54), for
harness_changes.DETECT_CHANGES: {case: (new value, reason)}. Each was a wrong
or doubtful answer (``id/Apache-1.1/id_distorted`` read as ``Apache-1.0``,
``id/AFL-2.1/id_distorted`` as ``AFL-2.0``); the value was cut."""

_NONE = "-\t-\t-\t-"
_CUT = (
    "the distorted ID is cut: a bare major the List has another minor of"
    " (`version ambiguous`) or a dash joined to the end (`character dropped`);"
    " it was read as a neighbour or a shorter ID (item 54)"
)

CUTVERSION_CHANGES: dict[str, tuple[str, str]] = {
    "id/AFL-2.1/id_distorted": (_NONE, _CUT),
    "id/Apache-1.1/id_distorted": (_NONE, _CUT),
    "id/CC-BY-3.0-US/id_distorted": (_NONE, _CUT),
    "id/CC-BY-NC-SA-2.0-DE/id_distorted": (_NONE, _CUT),
    "id/CC-BY-NC-SA-2.0-UK/id_distorted": (_NONE, _CUT),
    "id/CDDL-1.0/id_distorted": (_NONE, _CUT),
    "id/EUPL-1.0/id_distorted": (_NONE, _CUT),
    "id/MIT-STK/id_distorted": (_NONE, _CUT),
    "id/MIT-feh/id_distorted": (_NONE, _CUT),
    "id/OSL-2.0/id_distorted": (_NONE, _CUT),
    "value/LGPLv2": (
        _NONE,
        (
            "`LGPLv2` writes only the major: `LGPL-2.0` and `LGPL-2.1` are both"
            " on the List, so it names none (`version ambiguous`); it was"
            " `LGPL-2.0`"
        ),
    ),
}
