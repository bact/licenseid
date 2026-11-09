# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``resolve()`` answered on 0.8.3 for each value of
``slash_values.REFUSED``: expression, category, reason, steps as (kind,
detail) and operands as (text, span, expression, reason). Recorded on
``main`` (e764d88) before ``resolveslash`` existed; a value here answers the
same now, byte for byte. Generated once; do not edit by hand."""

from typing import Any

PINS: dict[str, dict[str, Any]] = {
    "zlib/libpng": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("zlib/libpng", (0, 11), None, "not an SPDX operator: /")],
    },
    "mit/apache-2.0": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("mit/apache-2.0", (0, 14), None, "not an SPDX operator: /")],
    },
    "MIT/apache-2.0": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/apache-2.0", (0, 14), None, "not an SPDX operator: /")],
    },
    "MIT/Apache": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/Apache", (0, 10), None, "not an SPDX operator: /")],
    },
    "Apache2/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("Apache2/MIT", (0, 11), None, "not an SPDX operator: /")],
    },
    "Apache 2.0/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: Apache 2.0/MIT",
        "steps": [],
        "operands": [("Apache 2.0/MIT", (0, 14), None, "not found: Apache 2.0/MIT")],
    },
    "GPLv3+/BSD": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: GPLv3+/BSD",
        "steps": [],
        "operands": [("GPLv3+/BSD", (0, 10), None, "not found: GPLv3+/BSD")],
    },
    "BSD/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("BSD/MIT", (0, 7), None, "not an SPDX operator: /")],
    },
    "TCL/TK": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("TCL/TK", (0, 6), None, "not an SPDX operator: /")],
    },
    "MIT/NONE": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/NONE", (0, 8), None, "not an SPDX operator: /")],
    },
    "MIT/X11": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/X11", (0, 7), None, "not an SPDX operator: /")],
    },
    "MIT/Classpath-exception-2.0": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [
            ("MIT/Classpath-exception-2.0", (0, 27), None, "not an SPDX operator: /")
        ],
    },
    "LicenseRef-a/LicenseRef-b": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [
            ("LicenseRef-a/LicenseRef-b", (0, 25), None, "not an SPDX operator: /")
        ],
    },
    "LicenseRef-x+/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: LicenseRef-x+/MIT",
        "steps": [],
        "operands": [
            ("LicenseRef-x+/MIT", (0, 17), None, "not found: LicenseRef-x+/MIT")
        ],
    },
    "DocumentRef-d:LicenseRef-x/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: DocumentRef-d:LicenseRef-x/MIT",
        "steps": [],
        "operands": [
            (
                "DocumentRef-d:LicenseRef-x/MIT",
                (0, 30),
                None,
                "not found: DocumentRef-d:LicenseRef-x/MIT",
            )
        ],
    },
    "licenseref-x/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("licenseref-x/MIT", (0, 16), None, "not an SPDX operator: /")],
    },
    "MIT//ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: //",
        "steps": [],
        "operands": [("MIT//ISC", (0, 8), None, "not an SPDX operator: //")],
    },
    "/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "character dropped: U+002F",
        "steps": [("drop", "U+002F")],
        "operands": [("/MIT", (0, 4), None, "character dropped: U+002F")],
    },
    "MIT/": {
        "expression": None,
        "category": "unresolved",
        "reason": "character dropped: U+002F",
        "steps": [("drop", "U+002F")],
        "operands": [("MIT/", (0, 4), None, "character dropped: U+002F")],
    },
    "Apache-2.0/MIT/": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: Apache-2.0/MIT/",
        "steps": [],
        "operands": [("Apache-2.0/MIT/", (0, 15), None, "not found: Apache-2.0/MIT/")],
    },
    "/": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: /",
        "steps": [],
        "operands": [("/", (0, 1), None, "not found: /")],
    },
    "//": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: //",
        "steps": [],
        "operands": [("//", (0, 2), None, "not found: //")],
    },
    "MIT/ISC OR Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [
            ("MIT/ISC", (0, 7), None, "not an SPDX operator: /"),
            ("Zlib", (11, 15), "Zlib", None),
        ],
    },
    "(MIT/ISC) AND Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [
            ("MIT/ISC", (1, 8), None, "not an SPDX operator: /"),
            ("Zlib", (14, 18), "Zlib", None),
        ],
    },
    "MIT/ISC; Apache-2.0": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/ISC; Apache-2.0", (0, 19), None, "not an SPDX operator: /")],
    },
    "MIT, ISC/Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: ,",
        "steps": [],
        "operands": [("MIT, ISC/Zlib", (0, 13), None, "not an SPDX operator: ,")],
    },
    "GPL-2.0-only WITH Classpath-exception-2.0/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "exception not found: Classpath-exception-2.0/MIT",
        "steps": [],
        "operands": [
            (
                "GPL-2.0-only WITH Classpath-exception-2.0/MIT",
                (0, 45),
                None,
                "exception not found: Classpath-exception-2.0/MIT",
            )
        ],
    },
    "MIT/Apache-2.0 or later": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/Apache-2.0 or later",
        "steps": [],
        "operands": [
            (
                "MIT/Apache-2.0 or later",
                (0, 23),
                None,
                "not found: MIT/Apache-2.0 or later",
            )
        ],
    },
    "GPL-2.0-only+/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: GPL-2.0-only+/MIT",
        "steps": [],
        "operands": [
            ("GPL-2.0-only+/MIT", (0, 17), None, "not found: GPL-2.0-only+/MIT")
        ],
    },
    "GPL-2.0-or-later+/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: GPL-2.0-or-later+/MIT",
        "steps": [],
        "operands": [
            ("GPL-2.0-or-later+/MIT", (0, 21), None, "not found: GPL-2.0-or-later+/MIT")
        ],
    },
    "LICENSE/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("LICENSE/MIT", (0, 11), None, "not an SPDX operator: /")],
    },
    "docs/licenses/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("docs/licenses/MIT", (0, 17), None, "not an SPDX operator: /")],
    },
    "./MIT/ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: ./MIT/ISC",
        "steps": [],
        "operands": [("./MIT/ISC", (0, 9), None, "not found: ./MIT/ISC")],
    },
    "opensource.org/licenses/MIT": {
        "expression": "MIT",
        "category": "license_url",
        "reason": None,
        "steps": [("license_url", "see also")],
        "operands": [("opensource.org/licenses/MIT", (0, 27), "MIT", None)],
    },
    "https://opensource.org/licenses/MIT": {
        "expression": "MIT",
        "category": "license_url",
        "reason": None,
        "steps": [("license_url", "see also")],
        "operands": [("https://opensource.org/licenses/MIT", (0, 35), "MIT", None)],
    },
    "https://example.com/MIT/ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: https://example.com/MIT/ISC",
        "steps": [],
        "operands": [
            (
                "https://example.com/MIT/ISC",
                (0, 27),
                None,
                "not found: https://example.com/MIT/ISC",
            )
        ],
    },
    "spdx:MIT/ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: spdx:MIT/ISC",
        "steps": [],
        "operands": [("spdx:MIT/ISC", (0, 12), None, "not found: spdx:MIT/ISC")],
    },
    "licenses.nuget.org/MIT": {
        "expression": "MIT",
        "category": "license_url",
        "reason": None,
        "steps": [("license_url", "id in path")],
        "operands": [("licenses.nuget.org/MIT", (0, 22), "MIT", None)],
    },
    "https://licenses.nuget.org/MIT": {
        "expression": "MIT",
        "category": "license_url",
        "reason": None,
        "steps": [("license_url", "id in path")],
        "operands": [("https://licenses.nuget.org/MIT", (0, 30), "MIT", None)],
    },
    "MIT\u2215ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT\u2215ISC",
        "steps": [],
        "operands": [("MIT\u2215ISC", (0, 7), None, "not found: MIT\u2215ISC")],
    },
    "MIT\uff0fISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT\uff0fISC",
        "steps": [],
        "operands": [("MIT\uff0fISC", (0, 7), None, "not found: MIT\uff0fISC")],
    },
    "MIT\u2044ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT\u2044ISC",
        "steps": [],
        "operands": [("MIT\u2044ISC", (0, 7), None, "not found: MIT\u2044ISC")],
    },
    "MIT\u29f8ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT\u29f8ISC",
        "steps": [],
        "operands": [("MIT\u29f8ISC", (0, 7), None, "not found: MIT\u29f8ISC")],
    },
    "MIT\\ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT\\ISC",
        "steps": [],
        "operands": [("MIT\\ISC", (0, 7), None, "not found: MIT\\ISC")],
    },
    "MIT%2FISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT%2FISC",
        "steps": [],
        "operands": [("MIT%2FISC", (0, 9), None, "not found: MIT%2FISC")],
    },
    "MIT\xa0/\xa0ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT\xa0/\xa0ISC", (0, 9), None, "not an SPDX operator: /")],
    },
    "MIT\n/\nISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT\n/\nISC", (0, 9), None, "not an SPDX operator: /")],
    },
    "MIT /\nISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT /\nISC", (0, 9), None, "not an SPDX operator: /")],
    },
    "MIT/ ISC/": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/ ISC/",
        "steps": [],
        "operands": [("MIT/ ISC/", (0, 9), None, "not found: MIT/ ISC/")],
    },
    "NCSA": {
        "expression": "NCSA",
        "category": "exact",
        "reason": None,
        "steps": [],
        "operands": [("NCSA", (0, 4), "NCSA", None)],
    },
    "University of Illinois/NCSA": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: University of Illinois/NCSA",
        "steps": [],
        "operands": [
            (
                "University of Illinois/NCSA",
                (0, 27),
                None,
                "not found: University of Illinois/NCSA",
            )
        ],
    },
    "TCL/TK ": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [("trim", None)],
        "operands": [("TCL/TK", (0, 6), None, "not an SPDX operator: /")],
    },
    "MIT/ISC AND Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [
            ("MIT/ISC", (0, 7), None, "not an SPDX operator: /"),
            ("Zlib", (12, 16), "Zlib", None),
        ],
    },
    "MIT/\u041cIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/\u041cIT",
        "steps": [],
        "operands": [("MIT/\u041cIT", (0, 7), None, "not found: MIT/\u041cIT")],
    },
    "MIT/ISC?": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/ISC?",
        "steps": [],
        "operands": [("MIT/ISC?", (0, 8), None, "not found: MIT/ISC?")],
    },
    "MIT/ISC/?": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/ISC/?",
        "steps": [],
        "operands": [("MIT/ISC/?", (0, 9), None, "not found: MIT/ISC/?")],
    },
    "MIT / / ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT / / ISC",
        "steps": [],
        "operands": [("MIT / / ISC", (0, 11), None, "not found: MIT / / ISC")],
    },
    "M/IT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("M/IT", (0, 4), None, "not an SPDX operator: /")],
    },
    "MIT/(ISC)": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/(ISC)",
        "steps": [],
        "operands": [("MIT/(ISC)", (0, 9), None, "not found: MIT/(ISC)")],
    },
    "(MIT)/ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: (MIT)/ISC",
        "steps": [],
        "operands": [("(MIT)/ISC", (0, 9), None, "not found: (MIT)/ISC")],
    },
    '"MIT"/ISC': {
        "expression": None,
        "category": "unresolved",
        "reason": 'not found: "MIT"/ISC',
        "steps": [],
        "operands": [('"MIT"/ISC', (0, 9), None, 'not found: "MIT"/ISC')],
    },
    "MIT/ISC WITH x": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/ISC WITH x",
        "steps": [],
        "operands": [("MIT/ISC WITH x", (0, 14), None, "not found: MIT/ISC WITH x")],
    },
    "MIT/GPL-2.0-only+": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/GPL-2.0-only+",
        "steps": [],
        "operands": [
            ("MIT/GPL-2.0-only+", (0, 17), None, "not found: MIT/GPL-2.0-only+")
        ],
    },
    "MIT/ISC\u2215Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/ISC\u2215Zlib",
        "steps": [],
        "operands": [
            ("MIT/ISC\u2215Zlib", (0, 12), None, "not found: MIT/ISC\u2215Zlib")
        ],
    },
    "MIT\u2215ISC/Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT\u2215ISC/Zlib",
        "steps": [],
        "operands": [
            ("MIT\u2215ISC/Zlib", (0, 12), None, "not found: MIT\u2215ISC/Zlib")
        ],
    },
    "MIT/ISC\uff0fZlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/ISC\uff0fZlib",
        "steps": [],
        "operands": [
            ("MIT/ISC\uff0fZlib", (0, 12), None, "not found: MIT/ISC\uff0fZlib")
        ],
    },
    "Zlib/Libpng": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("Zlib/Libpng", (0, 11), None, "not an SPDX operator: /")],
    },
    "Libpng/Zlib": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("Libpng/Zlib", (0, 11), None, "not an SPDX operator: /")],
    },
    "X11/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("X11/MIT", (0, 7), None, "not an SPDX operator: /")],
    },
    "MIT/X11/ISC": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/X11/ISC", (0, 11), None, "not an SPDX operator: /")],
    },
    "MIT/ISC/X11": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/ISC/X11", (0, 11), None, "not an SPDX operator: /")],
    },
    "MIT/X11/MIT": {
        "expression": None,
        "category": "unresolved",
        "reason": "not an SPDX operator: /",
        "steps": [],
        "operands": [("MIT/X11/MIT", (0, 11), None, "not an SPDX operator: /")],
    },
    "MIT/X11+": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT/X11+",
        "steps": [],
        "operands": [("MIT/X11+", (0, 8), None, "not found: MIT/X11+")],
    },
    "MIT+/X11": {
        "expression": None,
        "category": "unresolved",
        "reason": "not found: MIT+/X11",
        "steps": [],
        "operands": [("MIT+/X11", (0, 8), None, "not found: MIT+/X11")],
    },
}
