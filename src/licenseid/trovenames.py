# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The trove classifiers of the ``License ::`` family, as data.

PyPI projects declare a licence by classifier, for example
``License :: OSI Approved :: MIT License``. The classifier list is closed
(PyPA's ``trove-classifiers``), so each name is decided here once and the
resolver never guesses in free text. Standard library only.

A name is decided by reading it literally, never by what its licence
usually means:

``stated``
    The name states one licence, with its version and its grant if the
    licence has them (``... v3 or later (GPLv3+)`` is ``GPL-3.0-or-later``).
``assumed``
    The name states a bare deprecated ID, as ``GPL-2.0`` does (``... v2
    (GPLv2)`` has a version but no "only" and no "or later"). The existing
    policy applies: the ID is the answer, read as written, and its
    candidates are the ``-only`` and ``-or-later`` IDs.
``none``
    The name names no single licence: a category (``OSI Approved``), a
    family (``BSD License``), a name without a version where the List holds
    several, or a licence with no SPDX ID (``Public Domain``).

``Apache Software License`` and ``Python Software Foundation License`` are
``none`` here: they imply ``Apache-2.0`` and ``PSF-2.0`` by usage, not by
what they write (rule T4, deferred: Q3).
"""

import re
from typing import Final, Literal, NamedTuple

Reading = Literal["stated", "assumed", "none"]


class TroveEntry(NamedTuple):
    """What one classifier name says.

    Attributes:
        ids: The SPDX IDs the name reads as; empty for ``none``.
        reading: How firmly the name says it.
    """

    ids: tuple[str, ...]
    reading: Reading


def _stated(spdx_id: str) -> TroveEntry:
    return TroveEntry((spdx_id,), "stated")


def _assumed(spdx_id: str) -> TroveEntry:
    return TroveEntry((spdx_id,), "assumed")


_NONE: Final = TroveEntry((), "none")

# Key: the last path segment of the classifier. The comment on an entry gives
# a judgement call. First the classifiers outside OSI Approved, then those
# under it, then the last three outside it.
TROVE_NAMES: Final[dict[str, TroveEntry]] = {
    # License :: ...
    "Aladdin Free Public License (AFPL)": _stated("Aladdin"),  # the List's name
    "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": _stated("CC0-1.0"),
    "CeCILL-B Free Software License Agreement (CECILL-B)": _stated("CECILL-B"),
    "CeCILL-C Free Software License Agreement (CECILL-C)": _stated("CECILL-C"),
    "DFSG approved": _NONE,  # a category
    "Eiffel Forum License (EFL)": _NONE,  # no version; EFL-1.0 and EFL-2.0
    "Free For Educational Use": _NONE,  # no SPDX ID
    "Free For Home Use": _NONE,  # no SPDX ID
    "Free To Use But Restricted": _NONE,  # no SPDX ID
    "Free for non-commercial use": _NONE,  # no SPDX ID
    "Freely Distributable": _NONE,  # no SPDX ID
    "Freeware": _NONE,  # no SPDX ID
    "GUST Font License 1.0": _NONE,  # not in the List
    "GUST Font License 2006-09-30": _NONE,  # not in the List
    "Netscape Public License (NPL)": _NONE,  # no version; NPL-1.0 and NPL-1.1
    "Nokia Open Source License (NOKOS)": _stated("Nokia"),  # the List's name
    "OSI Approved": _NONE,  # a category, not a licence (rule T1)
    # License :: OSI Approved :: ...
    "Academic Free License (AFL)": _NONE,  # no version; AFL-1.1 to AFL-3.0
    "Apache Software License": _NONE,  # by usage only (T4, Q3)
    "Apple Public Source License": _NONE,  # no version; APSL-1.0 to APSL-2.0
    "Artistic License": _NONE,  # no version; Artistic-1.0 and Artistic-2.0
    "Attribution Assurance License": _stated("AAL"),  # the List's name
    "BSD License": _NONE,  # a family
    "Blue Oak Model License (BlueOak-1.0.0)": _stated("BlueOak-1.0.0"),
    "Boost Software License 1.0 (BSL-1.0)": _stated("BSL-1.0"),
    "CEA CNRS Inria Logiciel Libre License, version 2.1 (CeCILL-2.1)": _stated(
        "CECILL-2.1"
    ),  # the ID in brackets is spelt CECILL- in the List
    "CMU License (MIT-CMU)": _stated("MIT-CMU"),  # the List's name
    "Common Development and Distribution License 1.0 (CDDL-1.0)": _stated("CDDL-1.0"),
    "Common Public License": _NONE,  # no version, though only CPL-1.0 exists
    "Eclipse Public License 1.0 (EPL-1.0)": _stated("EPL-1.0"),
    "Eclipse Public License 2.0 (EPL-2.0)": _stated("EPL-2.0"),
    "Educational Community License, Version 2.0 (ECL-2.0)": _stated("ECL-2.0"),
    "Eiffel Forum License": _NONE,  # no version; EFL-1.0 and EFL-2.0
    "European Union Public Licence 1.0 (EUPL 1.0)": _stated("EUPL-1.0"),
    "European Union Public Licence 1.1 (EUPL 1.1)": _stated("EUPL-1.1"),
    "European Union Public Licence 1.2 (EUPL 1.2)": _stated("EUPL-1.2"),
    "GNU Affero General Public License v3": _assumed("AGPL-3.0"),  # bare, deprecated
    "GNU Affero General Public License v3 or later (AGPLv3+)": _stated(
        "AGPL-3.0-or-later"
    ),
    "GNU Free Documentation License (FDL)": _NONE,  # no version
    "GNU General Public License (GPL)": _NONE,  # no version
    "GNU General Public License v2 (GPLv2)": _assumed("GPL-2.0"),  # bare, deprecated
    "GNU General Public License v2 or later (GPLv2+)": _stated("GPL-2.0-or-later"),
    "GNU General Public License v3 (GPLv3)": _assumed("GPL-3.0"),  # bare, deprecated
    "GNU General Public License v3 or later (GPLv3+)": _stated("GPL-3.0-or-later"),
    # Q23: the maintainer's special case, because LGPL is widespread. "Lesser
    # v2" contradicts itself (LGPL-2.0 is the "Library" GPL, the "Lesser" one
    # is 2.1), but the version is plainly 2, so it is read as written: the
    # bare deprecated ID. No other self-contradicting name is read this way:
    # the "v2 or later" name below stays none.
    "GNU Lesser General Public License v2 (LGPLv2)": _assumed("LGPL-2.0"),
    "GNU Lesser General Public License v2 or later (LGPLv2+)": _NONE,  # as Q23, P45
    "GNU Lesser General Public License v3 (LGPLv3)": _assumed("LGPL-3.0"),
    "GNU Lesser General Public License v3 or later (LGPLv3+)": _stated(
        "LGPL-3.0-or-later"
    ),
    "GNU Library or Lesser General Public License (LGPL)": _NONE,  # two licences
    "Historical Permission Notice and Disclaimer (HPND)": _stated("HPND"),
    "IBM Public License": _NONE,  # no version, though only IPL-1.0 exists
    "ISC License (ISCL)": _stated("ISC"),
    "MIT License": _stated("MIT"),
    "MIT No Attribution License (MIT-0)": _stated("MIT-0"),
    "MirOS License (MirOS)": _stated("MirOS"),
    "Motosoto License": _stated("Motosoto"),  # the List's name
    "Mozilla Public License 1.0 (MPL)": _stated("MPL-1.0"),  # the version is 1.0
    "Mozilla Public License 1.1 (MPL 1.1)": _stated("MPL-1.1"),
    "Mozilla Public License 2.0 (MPL 2.0)": _stated("MPL-2.0"),
    "Mulan Permissive Software License v2 (MulanPSL-2.0)": _stated("MulanPSL-2.0"),
    "NASA Open Source Agreement v1.3 (NASA-1.3)": _stated("NASA-1.3"),
    "Nethack General Public License": _stated("NGPL"),  # the List's name
    "Nokia Open Source License": _stated("Nokia"),  # the List's name
    "Open Group Test Suite License": _stated("OGTSL"),  # the List's name
    "Open Software License 3.0 (OSL-3.0)": _stated("OSL-3.0"),
    "PostgreSQL License": _stated("PostgreSQL"),  # the List's name
    "Python License (CNRI Python License)": _stated("CNRI-Python"),  # in brackets
    "Python Software Foundation License": _NONE,  # by usage only (T4, Q3)
    "Qt Public License (QPL)": _NONE,  # no version; the List has "Q Public"
    "Ricoh Source Code Public License": _stated("RSCPL"),  # the List's name
    "SIL Open Font License 1.1 (OFL-1.1)": _stated("OFL-1.1"),
    "Sleepycat License": _stated("Sleepycat"),  # the List's name
    "Sun Public License": _NONE,  # no version, though only SPL-1.0 exists
    "The Unlicense (Unlicense)": _stated("Unlicense"),
    "Universal Permissive License (UPL)": _NONE,  # no version; UPL-1.0 only
    "University of Illinois/NCSA Open Source License": _stated("NCSA"),
    "Vovida Software License 1.0": _stated("VSL-1.0"),
    "W3C License": _NONE,  # no version; W3C, W3C-19980720, W3C-20150513 (Q22)
    "Zero-Clause BSD (0BSD)": _stated("0BSD"),
    "Zope Public License": _NONE,  # no version; ZPL-1.1 to ZPL-2.1
    "zlib/libpng License": _NONE,  # two licences, Zlib and Libpng
    # License :: ... again
    "Other/Proprietary License": _NONE,  # no SPDX ID
    "Public Domain": _NONE,  # no SPDX ID
    "Repoze Public License": _NONE,  # not in the List
}

_RE_PATH_SEPARATOR: Final = re.compile(r"\s*::\s*")
_OSI_SEGMENT: Final = "OSI Approved"


def strip_trove_path(text: str) -> str | None:
    """Return the classifier name inside a ``License ::`` path, or ``None``.

    Rule T1. ``License :: OSI Approved :: X`` and the short path
    ``License :: X`` (a classifier with no ``OSI Approved`` segment) give
    ``X``. White space round ``::`` is not significant. Anything else gives
    ``None``: no ``License ::`` prefix, a path that ends at ``OSI Approved``
    (a category, not a licence), an empty name or a deeper path.

    Args:
        text: A declared licence value.

    Returns:
        The name, not looked up, or ``None`` if the text is no such path.
    """
    parts = _RE_PATH_SEPARATOR.split(text.strip())
    if len(parts) < 2 or parts[0] != "License":
        return None
    if parts[1] == _OSI_SEGMENT:
        parts = parts[2:]
    else:
        parts = parts[1:]
    if len(parts) != 1 or not parts[0]:
        return None
    return parts[0]
