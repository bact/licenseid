# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The deprecated SPDX IDs licenseid reads by a table of its own: a "+"
form, a bare ID and a "-with-" ID, each with what it reads it as.

Data only (no import): :mod:`licenseid.identifiers` and the variant
readers read them. The List's own renames come from the database
(``get_deprecated_mappings``).
"""

__all__ = [
    "BARE_TO_OR_LATER",
    "DEPRECATED_BARE_LICENSE_IDS",
    "DEPRECATED_SPDX_LICENSE_IDS",
    "DEPRECATED_WITH_IDS",
]

# Deprecated SPDX License IDs using the '+' expression token.
# The SPDX '+' operator means "or any later version" (SPDX Spec §10.1).
# These can be resolved to canonical form with certainty because the '+'
# unambiguously indicates the -or-later variant.
#
# Reference: SPDX Specification v3.0, Annex D — SPDX License Expressions
#   https://spdx.github.io/spdx-spec/v3.0/annexes/spdx-license-expressions/
DEPRECATED_SPDX_LICENSE_IDS: dict[str, str] = {
    "GPL-1.0+": "GPL-1.0-or-later",
    "GPL-2.0+": "GPL-2.0-or-later",
    "GPL-3.0+": "GPL-3.0-or-later",
    "LGPL-2.0+": "LGPL-2.0-or-later",
    "LGPL-2.1+": "LGPL-2.1-or-later",
    "LGPL-3.0+": "LGPL-3.0-or-later",
    "AGPL-1.0+": "AGPL-1.0-or-later",
    "AGPL-3.0+": "AGPL-3.0-or-later",
    "GFDL-1.1+": "GFDL-1.1-or-later",
    "GFDL-1.2+": "GFDL-1.2-or-later",
    "GFDL-1.3+": "GFDL-1.3-or-later",
}

# The -only twin of each bare deprecated ID (no '+'). A bare ID is ambiguous:
# GPL-2.0-only and GPL-2.0-or-later share one text, and only the grant ("version
# 2 only", "any later version") tells them apart. The -only twin is what the
# ``only`` variant reads it as, and a reader outside ``detect()``; ``auto``
# keeps a declared bare ID as written (licenseid.variants).
DEPRECATED_BARE_LICENSE_IDS: dict[str, str] = {
    "GPL-1.0": "GPL-1.0-only",
    "GPL-2.0": "GPL-2.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "LGPL-2.0": "LGPL-2.0-only",
    "LGPL-2.1": "LGPL-2.1-only",
    "LGPL-3.0": "LGPL-3.0-only",
    "AGPL-1.0": "AGPL-1.0-only",
    "AGPL-3.0": "AGPL-3.0-only",
    "GFDL-1.1": "GFDL-1.1-only",
    "GFDL-1.2": "GFDL-1.2-only",
    "GFDL-1.3": "GFDL-1.3-only",
}

# Mapping of deprecated "-with-" IDs to their modern counterparts
DEPRECATED_WITH_IDS: dict[str, str] = {
    "GPL-2.0-with-font-exception": "GPL-2.0-only WITH Font-exception-2.0",
    "GPL-2.0-with-GCC-exception": "GPL-2.0-only WITH GCC-exception-2.0",
    "GPL-2.0-with-autoconf-exception": "GPL-2.0-only WITH Autoconf-exception-2.0",
    "GPL-2.0-with-bison-exception": "GPL-2.0-only WITH Bison-exception-2.2",
    "GPL-3.0-with-autoconf-exception": "GPL-3.0-only WITH Autoconf-exception-3.0",
    "GPL-3.0-with-GCC-exception": "GPL-3.0-only WITH GCC-exception-3.1",
    "GPL-2.0-with-classpath-exception": "GPL-2.0-only WITH Classpath-exception-2.0",
}

# Lookup: bare deprecated ID → canonical or-later form.
# Derived from DEPRECATED_SPDX_LICENSE_IDS by stripping the trailing "+".
BARE_TO_OR_LATER: dict[str, str] = {
    k[:-1]: v for k, v in DEPRECATED_SPDX_LICENSE_IDS.items()
}
