# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden ``detect()`` answers moved by the rules that doubt a name hit
(``licenseid.namehits`` and ``namerules``, roadmap item 47), for
``harness_changes.DETECT_CHANGES``: ``{case: (new value, reason)}``. Each was
found by name at 1.0, not exact. ``GNU General Public License v3`` moved before
(``harness_changes_nametier``) and moves again: ``v3`` is read as ``v3.0``.
``GNU Lesser General Public License v3`` moved there too and is back to its
golden answer, so it is no longer listed.
The ``mixed`` rows are sections of a file: a hit that is doubted is dropped
there, and Tier 1 runs on the section as before; a name written whole beats
names made of scattered words (``_WRITTEN``)."""

_NONE = "-\t-\t-\t-"
_DROPPED = (
    "name tier: a hit the rest of the input doubts (the golden ID was right; "
    "the full List gives none in 0.8.4 and now)"
)
_SPECIFIC = "name tier: the most specific of tied names (was a less specific one)"
_STILL_WRONG = "name tier: the most specific of tied names (was another wrong one)"
_WRITTEN = "name tier: the name written whole beats scattered words (was wrong)"
_V3 = "name tier: v3 is v3.0, the -only guess, variant not stated"

NAME_TIER2_CHANGES: dict[str, tuple[str, str]] = {
    "id/libpng-1.6.35/id_distorted": (
        _NONE,
        _DROPPED,
    ),
    "mixed/mixed-content/AFL-1.2/lib_mock_afl-1.2_0.py": (
        "AFL-1.2\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/AFL-1.2/lib_mock_afl-1.2_1.py": (
        "AFL-1.2\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/APSL-2.0/pubspec.yaml": (
        "APSL-2.0\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/Apache-1.1/pubspec.yaml": (
        "Apache-1.1\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/Apache-2.0/pubspec.yaml": (
        "Apache-2.0\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/Artistic-1.0-Perl/lib_mock_artistic-1.0-perl_1.py": (
        "Artistic-1.0-Perl\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/Artistic-1.0-Perl/lib_mock_artistic-1.0-perl_2.py": (
        "Artistic-1.0-Perl\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/Artistic-1.0-Perl/pubspec.yaml": (
        "Artistic-1.0-Perl\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/BSD-3-Clause/package.json": (
        "BSD-3-Clause\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/CC-BY-NC-1.0/3_pubspec.yaml": (
        "CC-BY-NC-1.0\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/CC-BY-NC-1.0/pubspec.yaml": (
        "CC-BY-NC-1.0\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/CDDL-1.1/pubspec.yaml": (
        "CDDL-1.1\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/CERN-OHL-1.2/pubspec.yaml": (
        "CERN-OHL-1.2\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/EUPL-1.2/lib_mock_eupl-1.2_1.py": (
        "EUPL-1.2\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/EUPL-1.2/lib_mock_eupl-1.2_3.py": (
        "EUPL-1.2\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/HPND-DEC/lib_mock_hpnd-dec_0.py": (
        "HPND-DEC\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/LGPL-2.0-or-later/index.html": (
        "LGPL-2.0-or-later\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/MIT-STK/lib_mock_mit-stk_1.py": (
        "MIT-STK\tname\tno\t1.0000",
        _SPECIFIC,
    ),
    "mixed/mixed-content/MPL-2.0-no-copyleft-exception/pubspec.yaml": (
        "MPL-2.0-no-copyleft-exception\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/OFL-1.1-no-RFN/pubspec.yaml": (
        "OFL-1.1-no-RFN\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "mixed/mixed-content/OSL-3.0/pubspec.yaml": (
        "OSL-3.0\tname\tno\t1.0000",
        _WRITTEN,
    ),
    "name/HPND-DEC/name_distored": (
        _NONE,
        _DROPPED,
    ),
    "value/Apache License 2.0 OR MIT": (
        _NONE,
        _DROPPED,
    ),
    "value/GNU General Public License v3": (
        "GPL-3.0-only\tname\tno\t1.0000",
        _V3,
    ),
    "value/MIT -or- Apache License 2.0": (
        _NONE,
        _DROPPED,
    ),
    "value/MIT License, Apache License, Version 2.0": (
        _NONE,
        _DROPPED,
    ),
    "value/Universal Permissive License 1.0 or Apache License 2.0": (
        _NONE,
        _DROPPED,
    ),
    "value/zlib/libpng License": (
        _NONE,
        _DROPPED,
    ),
}
