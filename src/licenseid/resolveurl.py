# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A licence URL, read as the licence it names (issue #14).

Package metadata often declares its licence as a URL: a Maven POM's
``<url>``, NuGet's ``licenseUrl``, a PyPI ``License: https://...``. A URL is
keyed by :func:`licenseid.urlkey.url_key`, so its spellings compare as one
string, and read in this order:

1. A page whose path holds an ID (:data:`ID_PAGES`): the List's own
   (``spdx.org/licenses/<ID>``, with ``.html`` or ``.json``, and
   ``spdx:<ID>``), NuGet's, choosealicense's and ScanCode LicenseDB's. An
   exception's page is refused: an exception is no licence. A ScanCode key
   that is an SPDX ID of another licence (:data:`SCANCODE_NOT_SPDX`) is not
   read as that ID. On the List's own pages only, ``<ID>+`` is the licence
   with the "+" operator, as ``MIT+`` is read.
   On ``licenses.nuget.org`` the path may be a whole licence expression,
   URL-encoded (:mod:`licenseid.nugetpath`), read after the ID page.
2. A page of :data:`DUAL_PAGES`, reviewed by hand: a page the List gives one
   licence that offers a choice of several. Refused.
3. A page the List gives a licence in ``seeAlso``
   (:meth:`licenseid.listlookup.ListLookup.get_ids_by_url`): one licence,
   one after a rename, or a GNU family (``X``, ``X-only``, ``X-or-later``),
   which is the bare deprecated ``X``, ``assumed_only`` with both
   candidates, as the bare ID is read. A page of several other licences is
   refused (``url names several licences: ...``), and so is a page of
   exceptions only, or of a licence and an exception (``url names a licence
   with an exception: ...``), unless each licence is one of the List's old
   IDs of both (``GPL-2.0-with-classpath-exception``), read as it is. A List
   URL with a ``#fragment`` names a place on its page: the page of its owner
   and of the owners of the page itself; a page the List gives only with a
   fragment names no licence by itself.
4. A page of :data:`URL_ALIASES`, reviewed by hand: a page the List lacks,
   or one it gives a licence and its variants (MPL-2.0, OFL-1.1). An alias
   is read only where the List gives no page, or gives its ID among others.

Each reading is a ``license_url`` step from the URL to the ID, then the
steps of the ID read alone (:func:`licenseid.resolvetable.read_as`), so a
rename and a deprecation read as they do for the ID. A refusal claims the
value: no later reader guesses at it. A URL that names nothing reads as no
URL: ``not found``.

The URL is keyed once (linear in its length, :mod:`licenseid.urlkey`), and
its page found by one lookup in an index the list keeps per key function:
no scan, no ``LIKE``. Standard library and ``licenseid`` only.
"""

from collections.abc import Callable, Iterable
from typing import Final, NamedTuple

from licenseid.dropguard import trim_end_mark
from licenseid.errors import reason_detail
from licenseid.exprcanon import is_compound
from licenseid.listlookup import ListedUrl, ListLookup
from licenseid.nugetpath import DETAIL as _EXPRESSION
from licenseid.nugetpath import decoded_path, read_expression
from licenseid.plusoperator import plus_after_qualifier, strip_plus_operator
from licenseid.resolveleaf import Found, refuse
from licenseid.resolvertypes import Step, step
from licenseid.resolvetable import read_as
from licenseid.urlkey import url_key

_KIND: Final = "license_url"
_SEE_ALSO: Final = "see also"  # the detail of a step to a page of the List
_ALIAS: Final = "alias"
_SCANCODE: Final = "scancode-licensedb.aboutcode.org/"
_SPDX_PAGES: Final = "spdx.org/licenses/"
_QUALIFIERS: Final = ("-only", "-or-later")
# The List's old IDs of a licence with its exception, deprecated with no
# successor: GPL-2.0-with-classpath-exception, GPL-3.0-with-GCC-exception.
_COMBINED: Final = "-with-"
# What starts the index key of a List URL with a fragment (page_index_key):
# no key of url_key holds a "#", so it is told from every page key.
_PLACE: Final = "#"

#: The keys of a page whose last segment is an ID, by the detail of the
#: step that reads it.
ID_PAGES: Final[dict[str, str]] = {
    _SPDX_PAGES: "list page",
    "licenses.nuget.org/": "id in path",
    "choosealicense.com/licenses/": "id in path",
    _SCANCODE: "id in path",
}

#: The ScanCode LicenseDB keys that are, folded, an SPDX ID of another
#: licence (ScanCode's ``index.json``, read for the survey of 2026-11-08):
#: a ScanCode page of one of them is not read as that SPDX ID.
SCANCODE_NOT_SPDX: Final = frozenset(
    {
        "brian-gladman-3-clause",
        "bsd-2-clause-freebsd",
        "bsd-2-clause-netbsd",
        "bsl-1.0",
        "intel",
        "libtool-exception",
        "mvt-1.1",
        "net-snmp",
        "nokia-qt-exception-1.1",
        "openssl",
        "opl-1.0",
        "tpl-1.0",
        "x11",
    }
)


class UrlAlias(NamedTuple):
    """The licence a page names, and the page that shows it does."""

    license_id: str
    source: str


#: Pages, by key (:func:`licenseid.urlkey.url_key`), read as one licence.
URL_ALIASES: Final[dict[str, UrlAlias]] = {
    # Pages the List lacks, each declared by three packages or more, and
    # each showing exactly one licence and version (survey of 2026-11-08).
    "opensource.org/license/mit-license": UrlAlias(
        "MIT", "https://opensource.org/license/mit"
    ),
    "eclipse.org/org/documents/epl-v10": UrlAlias(
        "EPL-1.0", "https://www.eclipse.org/org/documents/epl-1.0/"
    ),
    "eclipse.org/org/documents/epl-2.0/epl-2.0": UrlAlias(
        "EPL-2.0", "https://www.eclipse.org/org/documents/epl-2.0/EPL-2.0.txt"
    ),
    "repository.jboss.org/licenses/apache-2.0": UrlAlias(
        "Apache-2.0", "https://repository.jboss.org/licenses/apache-2.0.txt"
    ),
    "aws.amazon.com/apache2.0": UrlAlias(
        "Apache-2.0", "https://aws.amazon.com/apache-2-0/"
    ),
    "opensource.org/license/cpl1-0": UrlAlias(
        "CPL-1.0", "https://opensource.org/license/cpl-1-0"
    ),
    # A deprecated ID with no successor on the List: it reads as the ID
    # itself does, deprecated_ambiguous, as the List's own Classpath page
    # (gnu.org/software/classpath/license) does.
    "openjdk.java.net/legal/gplv2+ce": UrlAlias(
        "GPL-2.0-with-classpath-exception", "https://openjdk.org/legal/gplv2+ce.html"
    ),
    # Pages the List gives a licence and its variants, read as the licence:
    # the page is the licence's, a variant only adds a notice to it. Keyed
    # from spdx-see-also.json (3.29.0), the keys that name the base with
    # its variants and nothing else:
    # - mozilla.org/MPL/2.0/ and opensource.org/license/MPL-2.0 name MPL-2.0
    #   and MPL-2.0-no-copyleft-exception;
    # - opensource.org/license/OFL-1.1 and the SIL page item_id=OFL_web name
    #   OFL-1.1, OFL-1.1-RFN and OFL-1.1-no-RFN.
    "mozilla.org/mpl/2.0": UrlAlias("MPL-2.0", "https://www.mozilla.org/MPL/2.0/"),
    "opensource.org/license/mpl-2-0": UrlAlias(
        "MPL-2.0", "https://opensource.org/license/MPL-2.0"
    ),
    "opensource.org/license/ofl-1-1": UrlAlias(
        "OFL-1.1", "https://opensource.org/license/OFL-1.1"
    ),
    "scripts.sil.org/cms/scripts/page?item_id=ofl_web": UrlAlias(
        "OFL-1.1", "https://scripts.sil.org/cms/scripts/page.php?item_id=OFL_web"
    ),
}


#: Pages, by key, that the List gives one licence but that offer a choice
#: of several: refused as ``url names several licences``, with the IDs of
#: the licences the page offers.
DUAL_PAGES: Final[dict[str, tuple[str, ...]]] = {
    # source: the GlassFish licence page, "CDDL+GPL_1_1", offers CDDL 1.1 or
    # GPL 2 with the Classpath exception; the List gives it to CDDL-1.1.
    "glassfish.java.net/public/cddl+gpl_1_1": (
        "CDDL-1.1",
        "GPL-2.0-with-classpath-exception",
    ),
    # source: GlassFish's LICENSE on javaee.github.io offers the same two;
    # the List gives it to CDDL-1.1.
    "javaee.github.io/glassfish/license": (
        "CDDL-1.1",
        "GPL-2.0-with-classpath-exception",
    ),
}


class _Named(NamedTuple):
    """The text a page names (an ID, or an expression), the detail of the
    step to it, and the reader of that text (:func:`read_as` for an ID)."""

    license_id: str
    detail: str
    read: Callable[[ListLookup, Step, Found], bool] = read_as


class _Refusal(NamedTuple):
    """A page that names no one licence, and why."""

    reason: str


def read_url(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text*, a whole value or an operand, as the licence the URL
    names into *found*; one pair of angle brackets around it comes off
    first, as a ``brackets`` step. True with ``unresolved`` and a reason for
    a page that names no one licence. False if *text* is no URL or names
    nothing."""
    url, steps = without_angle_brackets(text)
    key = url_key(url)
    if key is None:
        return False
    named = _named(db, key, url)
    if named is None:
        return False
    if isinstance(named, _Refusal):
        refuse(found, "unresolved", named.reason)
        return True
    lead = step(_KIND, True, url, named.license_id, named.detail)
    if not named.read(db, lead, found):
        return False  # the list read lacks the ID
    if found.expression is not None or found.steps:  # not a bare refusal
        found.steps[:0] = steps
    return True


def url_license_id(db: ListLookup, text: str) -> str | None:
    """The expression the URL *text* names, read as :func:`read_url` reads
    it, or None; if none, *text* is read once more without one end mark
    (``https://spdx.org/licenses/MIT.``). A compound is in brackets
    (``(ISC OR MIT)``), so a word of a tag that stands for it keeps its
    precedence beside ``AND``."""
    for candidate in (text, trim_end_mark(text)):
        found = Found()
        if candidate is not None and read_url(db, candidate, found):
            return _bracketed(found.expression)
    return None


def _bracketed(expression: str | None) -> str | None:
    """*expression* in brackets if it joins licences, else as it is."""
    if expression is not None and is_compound(expression):
        return f"({expression})"
    return expression


def without_angle_brackets(text: str) -> tuple[str, list[Step]]:
    """*text* without one pair of angle brackets around the whole of it
    (``<https://...>``, as RFC 3986 appendix C delimits a URL in text), and
    its ``brackets`` step; else *text* and no step."""
    if len(text) > 2 and text[0] == "<" and text[-1] == ">":
        inner = text[1:-1]
        return inner, [step("brackets", True, text, inner)]
    return text, []


def list_url_key(url: str) -> str | None:
    """The key of a URL the List gives a licence, or None for a URL with a
    fragment: ``gpl-faq.html#FontException`` names a place on a page, not
    the page (:func:`fragment_page_key`)."""
    return None if url.partition("#")[2] else url_key(url)


def fragment_page_key(url: str) -> str | None:
    """The key of the page of a List URL with a fragment (``Licensing/MIT``
    of ``Licensing/MIT#enna``), the fragment dropped as :func:`url_key`
    drops it; None for a URL with no fragment (:func:`list_url_key`)."""
    return url_key(url) if url.partition("#")[2] else None


def page_index_key(url: str) -> str | None:
    """The key a List URL is indexed by: :func:`list_url_key`, or ``#`` and
    :func:`fragment_page_key` for a URL with a fragment. One key function
    for both: the list keeps the index of one, and a second would build it
    again at every lookup."""
    page = fragment_page_key(url)
    return list_url_key(url) if page is None else _PLACE + page


def _named(db: ListLookup, key: str, url: str) -> _Named | _Refusal | None:
    """What the page of *key* (the key of *url*) names: an ID page first,
    then an expression in a NuGet path, the pages that offer a choice, the
    List's pages and the aliases; None for nothing."""
    by_id = _id_page(db, key)
    if by_id is not None:
        return by_id
    expression = decoded_path(url, key)
    if expression is not None:
        return _Named(expression, _EXPRESSION, read_expression)
    offered = DUAL_PAGES.get(key)
    if offered is not None:
        return _Refusal(f"url names several licences: {_listed(list(offered))}")
    return _listed_page(db, key)


def _listed_page(db: ListLookup, key: str) -> _Named | _Refusal | None:
    """What the List's pages of *key* name, or its alias; None for nothing.
    A page the List gives only with a fragment names no licence by itself
    (``gpl-faq.html``); one it gives with and without counts the owners of
    both (``Licensing/MIT``: ``mpich2``, ``MIT-enna`` and more)."""
    index = db.get_ids_by_url(page_index_key)
    page, places = index.get(key, ()), index.get(_PLACE + key, ())
    if places and not page:
        return None
    rows = [*page, *places]
    licences = _ids(rows, exceptions=False)
    exceptions = _ids(rows, exceptions=True)
    alias = URL_ALIASES.get(key)
    if alias is not None and (not rows or alias.license_id in licences):
        return _Named(alias.license_id, _ALIAS)
    if licences and exceptions and not all(_combined(db, i) for i in licences):
        named = [*sorted(licences), *sorted(exceptions)]
        detail = reason_detail(", ".join(named))
        return _Refusal(f"url names a licence with an exception: {detail}")
    if licences:
        return _licence_page(db, licences)
    if exceptions:
        return _Refusal(f"url names an exception: {_listed(exceptions)}")
    return None


def _licence_page(db: ListLookup, licences: list[str]) -> _Named | _Refusal:
    """The one licence of a page of *licences*, or the bare ID of their
    family; else a refusal of several licences."""
    one = _one_licence(db, licences) or _family_base(db, licences)
    if one is not None:
        return _Named(one, _SEE_ALSO)
    return _Refusal(f"url names several licences: {_listed(licences)}")


def _combined(db: ListLookup, license_id: str) -> bool:
    """Whether *license_id* is one of the List's old IDs of a licence with
    its exception (``GPL-2.0-with-classpath-exception``): deprecated, with
    no successor, read as it is beside its exception."""
    details = db.get_license_details(license_id)
    if details is None or details.get("superseded_by"):
        return False
    return bool(details.get("is_deprecated")) and _COMBINED in license_id


def _id_page(db: ListLookup, key: str) -> _Named | _Refusal | None:
    """The licence a page of :data:`ID_PAGES` names by its last segment, a
    refusal for an exception's page, or None (no such page, an ID of no
    licence and no exception, a ScanCode key of another licence)."""
    for prefix, detail in ID_PAGES.items():
        ident = key.removeprefix(prefix)
        if ident == key or not ident or "/" in ident or "?" in ident:
            continue
        if prefix == _SCANCODE and ident in SCANCODE_NOT_SPDX:
            return None
        licence = db.get_license_details(ident)
        if licence is not None:
            return _Named(licence["license_id"], detail)
        exception = db.get_exception_details(ident)
        if exception is not None:
            reason = f"url names an exception: {_listed([exception['exception_id']])}"
            return _Refusal(reason)
        return _plus_page(db, ident, detail) if prefix == _SPDX_PAGES else None
    return None


def _plus_page(db: ListLookup, ident: str, detail: str) -> _Named | None:
    """The List's page of a licence with the "+" operator (``MIT+``), named
    as that ID and its "+", so the leaf reads it as it reads ``MIT+``; None
    if *ident* ends in no "+" operator (``plusoperator``), or in one after a
    qualifier (``GPL-2.0-only+``), or its ID is no licence of the List.
    With no "+" operator, *base* is *ident*, which names no licence."""
    if plus_after_qualifier(ident):
        return None
    base = strip_plus_operator(ident)
    licence = db.get_license_details(base)
    return None if licence is None else _Named(f"{licence['license_id']}+", detail)


def _ids(rows: Iterable[ListedUrl], *, exceptions: bool) -> list[str]:
    """The IDs of the licences (or *exceptions*) of *rows*, once each, in
    List order."""
    return list(dict.fromkeys(r["id"] for r in rows if r["is_exception"] == exceptions))


def _one_licence(db: ListLookup, licences: list[str]) -> str | None:
    """The one licence *licences* name, a rename and its successor as one
    (``StandardML-NJ`` and ``SMLNJ``), or None."""
    if len(licences) == 1:
        return licences[0]
    successors = _successors(db, licences)
    return successors[0] if len(successors) == 1 else None


def _successors(db: ListLookup, licences: list[str]) -> list[str]:
    """*licences*, each renamed one as its successor, once each."""
    found = []
    for license_id in licences:
        details = db.get_license_details(license_id)
        successor = details.get("superseded_by") if details else None
        found.append(successor or license_id)
    return list(dict.fromkeys(found))


def _family_base(db: ListLookup, licences: list[str]) -> str | None:
    """The bare deprecated ID ``X`` when *licences*, renames followed, are
    ``X``, ``X-only`` and ``X-or-later`` (some of them) and the List split
    ``X`` with no successor (``GPL-3.0``); else None. The page is the text
    of all of them: which one the author meant, it does not say."""
    bases = {_unqualified(license_id) for license_id in _successors(db, licences)}
    if len(bases) != 1:
        return None
    details = db.get_license_details(bases.pop())
    if details is None or not details.get("is_deprecated"):
        return None
    if details.get("superseded_by"):
        return None
    return details["license_id"]


def _unqualified(license_id: str) -> str:
    """*license_id* without its ``-only`` or ``-or-later``."""
    for qualifier in _QUALIFIERS:
        if license_id.endswith(qualifier):
            return license_id[: -len(qualifier)]
    return license_id


def _listed(ids: list[str]) -> str:
    """*ids*, sorted, as the detail of a reason (one line, cut)."""
    return reason_detail(", ".join(sorted(ids)))
