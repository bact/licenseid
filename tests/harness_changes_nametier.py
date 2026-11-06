# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden ``detect()`` answers moved by the name tier no longer reading
words that a longer licence name only holds as that name
(``shorttext._partial_names``), for ``harness_changes.DETECT_CHANGES``:
``{case: (new value, reason)}``. Each was found by name at 1.0, not exact;
under ten words and refused by ``resolve()``, it now has no answer."""

_NONE = "-\t-\t-\t-"
_WRONG = "name tier: words a longer name only holds (was a wrong licence)"
_UNSTATED = "name tier: words a longer name only holds (was a version not stated, P47)"
_LOST = "name tier: words a longer name only holds (right answer lost, for resolve())"

_CASES: dict[str, str] = {
    "id/CC-BY-NC-1.0/id_distorted": _WRONG,  # "CC-BY-NC-" was CC-BY-NC-3.0
    "id/Spencer-94/id_distorted": _UNSTATED,  # "Spencer": 86, 94 or 99
    "name/GFDL-1.2-or-later/name_distored": _WRONG,  # was the invariants one
    "name/MS-PL/name_distored": _WRONG,  # "microsoft public" was MS-LPL
    "name/GPL-3.0-or-later/name_distored": _WRONG,  # was AGPL-3.0-or-later
    "value/'BSD'": _WRONG,  # 0BSD
    "value/2-clause BSD": _LOST,
    "value/2-clause BSD License": _LOST,
    "value/3-Clause BSD License": _LOST,
    "value/3-clause BSD": _LOST,
    "value/APACHE": _UNSTATED,  # Apache-1.0
    "value/Apache": _UNSTATED,
    "value/Apache License": _UNSTATED,
    "value/Artistic License": _UNSTATED,  # Artistic-1.0
    "value/BSD": _WRONG,  # 0BSD
    "value/BSD 3": _LOST,
    "value/BSD License": _WRONG,  # 0BSD
    "value/BSD license": _WRONG,  # 0BSD
    "value/BSD-3": _LOST,
    "value/FreeBSD": _WRONG,  # FreeBSD-DOC
    "value/FreeBSD License": _WRONG,  # FreeBSD-DOC
    "value/GNU Affero General Public License": _UNSTATED,  # AGPL-3.0-only
    "value/GNU GENERAL PUBLIC LICENSE": _WRONG,  # AGPL-3.0-only
    "value/GNU General Public License v3": _WRONG,  # AGPL-3.0-only
    "value/GNU Lesser General Public License v3": _LOST,  # LGPL-3.0-only
    "value/GNU Lesser General Public License v3+": _WRONG,  # -only, "+" dropped
    "value/GPL": _WRONG,  # BSD-Source-alt-GPL
    "value/LICENSE": _WRONG,  # 0BSD
    "value/MIT AND": _WRONG,  # HPND-MIT-disclaimer
    "value/Mozilla": _UNSTATED,  # MPL-1.0
    "value/New BSD": _LOST,
    "value/New BSD License": _LOST,
    "value/New BSD license": _LOST,
    "value/Public Domain": _WRONG,  # CC-PDDC
    "value/Public domain": _WRONG,
    "value/Python": _WRONG,  # CNRI-Python
    "value/Revised BSD License": _LOST,
    "value/Simplified BSD": _LOST,
    "value/W3C License": _UNSTATED,  # W3C of three dated versions
    "value/W3C SOFTWARE NOTICE AND LICENSE": _UNSTATED,
    "value/new BSD": _LOST,
    "value/zlib/libpng": _WRONG,  # zlib-acknowledgement
}

NAME_TIER_CHANGES: dict[str, tuple[str, str]] = {
    case: (_NONE, reason) for case, reason in _CASES.items()
}
