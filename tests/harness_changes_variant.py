# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden answers moved by the ``variant`` option (``licenseid.variants``,
roadmap item 52): a declared bare deprecated ID stays as written
(``GPL-3.0``, was ``GPL-3.0-only``), for ``harness_changes.DETECT_CHANGES``
(``{case: (new value, reason)}``) and ``CLI_CHANGES`` (``{case: (digest,
reason)}``). Loaded after ``harness_changes_exact``: a case both move has the
value of both."""

_KEPT = (
    "a declared bare deprecated ID stays as written, as resolve() gives it"
    " (was the -only guess, with a warning)"
)
_FIELD = "the record has a last field VARIANT_STATED (JSON variant_stated)"

VARIANT_CHANGES: dict[str, tuple[str, str]] = {
    "value/AGPL-3": ("AGPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/AGPL-3.0": ("AGPL-3.0\tid\tyes\t1.0000", _KEPT),
    "value/AGPLv3": ("AGPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/GNU Affero General Public License v3": (
        "AGPL-3.0\tname\tyes\t1.0000",
        _KEPT,
    ),
    "value/GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007": (
        "GPL-3.0\tname\tyes\t1.0000",
        _KEPT,
    ),
    "value/GNU General Public License v2 (GPLv2)": (
        "GPL-2.0\tname\tyes\t1.0000",
        _KEPT,
    ),
    "value/GNU General Public License v3 (GPLv3)": (
        "GPL-3.0\tname\tyes\t1.0000",
        _KEPT,
    ),
    "value/GNU Lesser General Public License v2 (LGPLv2)": (
        "LGPL-2.0\tname\tyes\t1.0000",
        _KEPT,
    ),
    "value/GNU Lesser General Public License v3 (LGPLv3)": (
        "LGPL-3.0\tname\tyes\t1.0000",
        _KEPT,
    ),
    "value/GPL 2": ("GPL-2.0\tid\tno\t1.0000", _KEPT),
    "value/GPL 3.0": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/GPL V3.0": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/GPL v2": ("GPL-2.0\tid\tno\t1.0000", _KEPT),
    "value/GPL v3": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/GPL-2.0": ("GPL-2.0\tid\tyes\t1.0000", _KEPT),
    "value/GPL-3": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/GPL-3.0": ("GPL-3.0\tid\tyes\t1.0000", _KEPT),
    "value/GPL-3.0 OR MIT": ("GPL-3.0 OR MIT\tid\tyes\t1.0000", _KEPT),
    "value/GPL2": ("GPL-2.0\tid\tno\t1.0000", _KEPT),
    "value/GPL3": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/GPLv2": ("GPL-2.0\tid\tno\t1.0000", _KEPT),
    "value/GPLv3": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/LGPL 2.1": ("LGPL-2.1\tid\tno\t1.0000", _KEPT),
    "value/LGPL 3": ("LGPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/LGPL v2.1": ("LGPL-2.1\tid\tno\t1.0000", _KEPT),
    "value/LGPL v3": ("LGPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/LGPL-2.1": ("LGPL-2.1\tid\tyes\t1.0000", _KEPT),
    "value/LGPL-3.0": ("LGPL-3.0\tid\tyes\t1.0000", _KEPT),
    "value/LGPL3": ("LGPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/LGPLv2": ("LGPL-2.0\tid\tno\t1.0000", _KEPT),
    "value/LGPLv3": ("LGPL-3.0\tid\tno\t1.0000", _KEPT),
    "value/apache-2.0 AND lgpl-2.1 and unrar and brian-gladman-3-clause": (
        "Apache-2.0 AND Brian-Gladman-3-Clause AND LGPL-2.1 AND UnRAR\tid\tyes\t1.0000",
        _KEPT,
    ),
    "value/gpl v3": ("GPL-3.0\tid\tno\t1.0000", _KEPT),
}

VARIANT_CLI_CHANGES: dict[str, tuple[str, str]] = {
    "detect-flag-id#json": ("67ddd708ed7b", _FIELD),
    "detect-flag-id#text": ("ee4ffdb25ff6", _FIELD),
    "detect-flag-id-plus#json": ("6314f06ef0f5", _FIELD),
    "detect-flag-id-plus#text": ("e0e3f7601ce4", _FIELD),
    "detect-flag-id-unknown#json": ("9b11577f8cdb", _FIELD),
    "detect-flag-id-unknown#text": ("85ea7d1f2222", _FIELD),
    "detect-id#json": ("ade16e266f93", _FIELD),
    "detect-id#text": ("7fe5699aa218", _FIELD),
    "detect-id-deprecated#json": ("0d8c6efeb292", _FIELD),
    "detect-id-deprecated#text": ("003882c276dc", _FIELD),
    "detect-name#json": ("282c9f409dab", _FIELD),
    "detect-name#text": ("a11cf3e08d58", _FIELD),
    "detect-stdin#json": ("7f6ff5a0356b", _FIELD),
    "detect-stdin#text": ("2630c152358c", _FIELD),
    "detect-tag#json": ("edb6db1811b0", _FIELD),
    "detect-tag#text": ("85a3451dd5ca", _FIELD),
    "detect-tag-or-later#json": ("30351ad724e2", _FIELD),
    "detect-tag-or-later#text": ("7979d17d2601", _FIELD),
    "detect-terse#json": ("e552f1eb8c5d", _FIELD),
    "detect-terse-no-answer#json": ("4bd2dffe9f79", _FIELD),
    "detect-terse-top-three#json": ("43bbab5fc147", _FIELD),
    "detect-text#json": ("43e740543041", _FIELD),
    "detect-text#text": ("462e6fccd119", _FIELD),
    "detect-text-no-answer#json": ("987d0f6593c4", _FIELD),
    "detect-text-no-answer#text": ("c240254795fa", _FIELD),
    "detect-top-three#json": ("56c88363e9de", _FIELD),
    "detect-top-three#text": ("2a1dad54cfdf", _FIELD),
    "detect-unreadable-text#json": ("521fd768c6e1", _FIELD),
    "detect-unreadable-text#text": ("1d51639ab32c", _FIELD),
}
