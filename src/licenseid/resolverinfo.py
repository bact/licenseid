# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Who took part in a ``resolve()`` answer and what it rests on: the
resolver, the expression parser (a component) and the list read.

Apart from ``licenseid.resolver`` so that the entry point stays small.
"""

import importlib
import importlib.metadata

from licenseid.listlookup import ListLookup
from licenseid.resolvertypes import SPDX_LIST, Component, ListInfo, ListSource, Resolver

# The kinds of step the SPDX License List supports; see ListInfo.provides.
_PROVIDES = ["deprecation", "ids", "names", "texts"]
_PARSER = "py-spdx-license"


def list_info(db: ListLookup, source: ListSource) -> ListInfo:
    """The description of the SPDX License List the lookup reads, and where
    it was read."""
    version = db.get_metadata().get("license_list_version")
    return {
        "id": SPDX_LIST,
        "name": "SPDX License List",
        "version": version,
        "source": source,
        "url": (
            None
            if version is None
            else f"https://github.com/spdx/license-list-data/releases/tag/v{version}"
        ),
        "license": "CC0-1.0",
        "provides": list(_PROVIDES),
        "id_authority": True,
    }


def resolver_info() -> Resolver:
    """Who resolved. The version is read at call time, as
    ``spdx_source`` reads it (``importlib``, not an import statement): the
    package exports ``licenseid.resolver``, so a static import of the package
    there would be a cycle."""
    version = str(importlib.import_module("licenseid").__version__)
    return {
        "name": "licenseid",
        "version": version,
        "url": f"https://github.com/bact/licenseid/releases/tag/v{version}",
        "purl": f"pkg:pypi/licenseid@{version}",
    }


def parser_info() -> Component:
    """The expression parser, ``py-spdx-license``, as a component: named in an
    answer whose expression it parsed. Its version is the installed one."""
    version = importlib.metadata.version(_PARSER)
    return {
        "name": _PARSER,
        "version": version,
        "url": f"https://pypi.org/project/{_PARSER}/{version}/",
        "purl": f"pkg:pypi/{_PARSER}@{version}",
    }
