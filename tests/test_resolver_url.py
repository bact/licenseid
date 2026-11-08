# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads a licence URL as its licence (``licenseid.resolveurl``,
issue #14), and ``detect()`` and the CLI answer it through ``resolve()``.

The tables are read on the database of the whole 3.29.0 List
(``corpus_db``); the positive one on the packaged list too. The List's own
pages, one by one, are in ``test_resolver_url_data.py``; the key in
``test_urlkey.py``.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import functools
from typing import NamedTuple

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, resolve
from licenseid.errors import reason_detail
from licenseid.resolvertypes import Resolution
from licenseid.resolveurl import URL_ALIASES

SEE, PAGE, PATH = "see also", "list page", "id in path"
APACHE_URL = "https://www.apache.org/licenses/LICENSE-2.0"


class Case(NamedTuple):
    """The ID a page names (``named``, the ``to`` of the ``license_url`` step),
    the expression it reads as, the step's detail, and the kinds of the steps
    before and after it and of the expansions."""

    expression: str
    named: str
    detail: str
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    expansions: tuple[str, ...] = ()


def _apache(detail: str, before: tuple[str, ...] = ()) -> Case:
    return Case("Apache-2.0", "Apache-2.0", detail, before)


def _mit(detail: str) -> Case:
    return Case("MIT", "MIT", detail)


POSITIVE: dict[str, Case] = {
    # The examples of the issue.
    "https://opensource.org/license/Apache-2.0": _apache(SEE),
    "https://opensource.org/license/apache-2.0": _apache(SEE),
    APACHE_URL: _apache(SEE),
    "https://spdx.org/licenses/Apache-2.0": _apache(PAGE),
    "https://spdx.org/licenses/Apache-2.0.html": _apache(PAGE),
    "https://scancode-licensedb.aboutcode.org/apache-2.0.html": _apache(PATH),
    "spdx:Apache-2.0": _apache(PAGE),
    # Spellings of one page, and what a value is wrapped in.
    APACHE_URL + ".txt": _apache(SEE),
    "http://www.apache.org/licenses/LICENSE-2.0.txt/": _apache(SEE),
    "www.apache.org/licenses/LICENSE-2.0": _apache(SEE),
    f"<{APACHE_URL}>": _apache(SEE, ("brackets",)),
    f"({APACHE_URL})": _apache(SEE, ("brackets",)),
    f'"{APACHE_URL}"': _apache(SEE, ("unquote",)),
    APACHE_URL + ",": _apache(SEE, ("separator",)),
    APACHE_URL + ".": _apache(SEE, ("separator",)),
    f"  {APACHE_URL} ": _apache(SEE, ("trim",)),
    # The hosts that name an ID in their path, and the OSI's two forms.
    "opensource.org/licenses/MIT": _mit(SEE),
    "opensource.org/license/mit/": _mit(SEE),
    "licenses.nuget.org/MIT": _mit(PATH),
    "choosealicense.com/licenses/mit/": _mit(PATH),
    "https://SPDX.ORG/LICENSES/MIT": _mit(PAGE),
    "https://spdx.org/licenses/mit": _mit(PAGE),
    # A CC deed and its legal code, the Eclipse page.
    "https://creativecommons.org/licenses/by/4.0/": Case("CC-BY-4.0", "CC-BY-4.0", SEE),
    "https://creativecommons.org/licenses/by/4.0/legalcode": Case(
        "CC-BY-4.0", "CC-BY-4.0", SEE
    ),
    "https://creativecommons.org/publicdomain/zero/1.0/legalcode": Case(
        "CC0-1.0", "CC0-1.0", SEE
    ),
    "eclipse.org/legal/epl-v10.html": Case("EPL-1.0", "EPL-1.0", SEE),
    # A rename is followed, as it is for the ID alone; so is a "+".
    "https://spdx.org/licenses/StandardML-NJ.html": Case(
        "SMLNJ", "StandardML-NJ", PAGE, after=("deprecated_equal_successor",)
    ),
    "https://www.smlnj.org/license.html": Case("SMLNJ", "SMLNJ", SEE),
    "https://spdx.org/licenses/GPL-2.0+.html": Case(
        "GPL-2.0-or-later", "GPL-2.0+", PAGE, expansions=("plus_to_or_later",)
    ),
    # The List's page of an ID with a "+" the List lacks: the ID and "+".
    "https://spdx.org/licenses/MIT+": Case("MIT+", "MIT+", PAGE),
    "https://spdx.org/licenses/mit+.html": Case("MIT+", "MIT+", PAGE),
    "spdx:MIT+": Case("MIT+", "MIT+", PAGE),
    "spdx:Apache-2.0+": Case("Apache-2.0+", "Apache-2.0+", PAGE),
}


@functools.cache
def _bundle() -> bytes:
    return fixture_bundle()


def _is_unresolved(got: Resolution) -> bool:
    return (got["expression"], got["category"], got["trust"]) == (
        None,
        "unresolved",
        "none",
    )


def _check_positive(got: Resolution, value: str, case: Case) -> None:
    assert (got["expression"], got["category"], got["trust"]) == (
        case.expression,
        "license_url",
        "resolver_rule",
    )
    assert [s["kind"] for s in got["steps"]] == [
        *case.before,
        "license_url",
        *case.after,
    ]
    (lead,) = (s for s in got["steps"] if s["kind"] == "license_url")
    assert (lead["detail"], lead["to"], lead["applied"]) == (
        case.detail,
        case.named,
        True,
    )
    assert lead["from"] in value
    assert [e["kind"] for e in got["expansions"]] == list(case.expansions)
    assert (got["candidates"], got["reason"]) == ([], None)


@pytest.mark.parametrize(("value", "case"), POSITIVE.items(), ids=list(POSITIVE))
def test_a_url_reads_as_the_licence_it_names(
    monkeypatch: pytest.MonkeyPatch,
    corpus_db: LicenseDatabase,
    value: str,
    case: Case,
) -> None:
    _check_positive(resolve(value, corpus_db), value, case)
    ship(monkeypatch, _bundle())
    packaged = resolve(value, source="packaged")
    _check_positive(packaged, value, case)
    assert packaged["lists"][0]["source"] == "packaged"


#: A GNU page names X, X+, X-only and X-or-later: the bare deprecated X,
#: as the bare ID is read, the guess left to the caller.
OPENJDK = (
    "https://github.com/openjdk/jdk/blob/"
    "6162e2c5213c5dd7c1127fd9616b543efa898962/LICENSE"
)
FAMILIES = {
    "https://www.gnu.org/licenses/gpl-3.0.html": "GPL-3.0",
    "https://www.gnu.org/licenses/gpl-3.0-standalone.html": "GPL-3.0",
    "https://opensource.org/license/GPL-3.0": "GPL-3.0",
    "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html": "LGPL-2.1",
    "https://www.gnu.org/licenses/agpl.txt": "AGPL-3.0",
    "https://opensource.org/license/AGPL-3.0": "AGPL-3.0",
    "http://www.affero.org/oagpl.html": "AGPL-1.0",
    # a page of -only and -or-later alone
    OPENJDK: "GPL-2.0",
}


@pytest.mark.parametrize(("value", "base"), FAMILIES.items(), ids=list(FAMILIES))
def test_a_family_page_is_the_bare_id_with_both_candidates(
    corpus_db: LicenseDatabase, value: str, base: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        base,
        "assumed_only",
        "none",
    )
    assert got["candidates"] == [f"{base}-only", f"{base}-or-later"]
    assert [(s["kind"], s["detail"]) for s in got["steps"]] == [("license_url", SEE)]
    assert [(e["kind"], e["applied"]) for e in got["expansions"]] == [
        ("assumed_only", False)
    ]
    alone = resolve(base, corpus_db)
    assert (alone["expression"], alone["category"]) == (base, "assumed_only")
    assert alone["candidates"] == got["candidates"]


def test_a_page_of_the_only_form_is_that_form(corpus_db: LicenseDatabase) -> None:
    got = resolve("https://opensource.org/license/GPL-3.0-only", corpus_db)
    assert (got["expression"], got["category"], got["candidates"]) == (
        "GPL-3.0-only",
        "license_url",
        [],
    )


#: A deprecated ID the List gives no successor, read as the ID is
#: (``deprecated_ambiguous``): by its own page, and by a page it shares with
#: its exception, where the List's old ID of both is read as it is.
CLASSPATH = "GPL-2.0-with-classpath-exception"
DEPRECATED = {
    f"https://spdx.org/licenses/{CLASSPATH}": CLASSPATH,
    "https://www.gnu.org/software/classpath/license.html": CLASSPATH,
    "https://www.gnu.org/licenses/gcc-exception-3.1.html": (
        "GPL-3.0-with-GCC-exception"
    ),
    "https://www.gnu.org/licenses/autoconf-exception-3.0.html": (
        "GPL-3.0-with-autoconf-exception"
    ),
    "http://ac-archive.sourceforge.net/doc/copyright.html": (
        "GPL-2.0-with-autoconf-exception"
    ),
    "https://spdx.org/licenses/wxWindows": "wxWindows",
}


@pytest.mark.parametrize(("value", "expression"), DEPRECATED.items())
def test_a_deprecated_id_with_no_successor_is_read_as_it_is(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["category"], got["trust"]) == ("deprecated_ambiguous", "list_data")
    assert got["expression"] == got["steps"][0]["to"] == expression
    assert got["steps"][0]["kind"] == "license_url"


def _exception(*ids: str) -> str:
    return f"url names an exception: {', '.join(ids)}"


def _several(*ids: str) -> str:
    return f"url names several licences: {', '.join(ids)}"


def _with(*ids: str) -> str:
    return f"url names a licence with an exception: {', '.join(ids)}"


FEDORA_MIT = "https://fedoraproject.org/wiki/Licensing/MIT"
FEDORA_FSFUL = "https://fedoraproject.org/wiki/Licensing/FSF_Unlimited_License"
PYTHON = "https://docs.python.org/3/license.html"
GLASSFISH = ("CDDL-1.1", CLASSPATH)


REFUSED = {
    # an exception is no licence: its page by ID, and a page of the List
    "https://spdx.org/licenses/Classpath-exception-2.0.html": _exception(
        "Classpath-exception-2.0"
    ),
    "spdx:Classpath-exception-2.0": _exception("Classpath-exception-2.0"),
    "https://licenses.nuget.org/Classpath-exception-2.0": _exception(
        "Classpath-exception-2.0"
    ),
    "https://scancode-licensedb.aboutcode.org/classpath-exception-2.0.html": (
        _exception("Classpath-exception-2.0")
    ),
    "https://swift.org/LICENSE.txt": _exception("Swift-exception"),
    "https://solderpad.org/licenses/SHL-2.1/": _exception("SHL-2.1"),
    "http://openjdk.java.net/legal/assembly-exception.html": _exception(
        "OpenJDK-assembly-exception-1.0"
    ),
    # a page of several licences
    "https://www.unicode.org/license.txt": _several("Unicode-3.0", "Unicode-DFS-2016"),
    "http://www.microsoft.com/opensource/licenses.mspx": _several("MS-PL", "MS-RL"),
    "https://forge.gouv.qc.ca/licence/liliq-p/": _several("LiLiQ-P-1.1", "LiLiQ-R-1.1"),
    "http://scripts.sil.org/cms/scripts/page.php?item_id=OFL10_web": _several(
        "OFL-1.0", "OFL-1.0-RFN", "OFL-1.0-no-RFN"
    ),
    # the reason is cut to 60 characters
    "https://www.gnu.org/licenses/fdl-1.3.txt": (
        _several("GFDL-1.3", "GFDL-1.3-invariants-only", "GFDL-1.3-invariants-or-l...")
    ),
    "https://web.mit.edu/kerberos/krb5-1.21/doc/mitK5license.html": (
        _several("BSD-2-Clause-first-lines", "Brian-Gladman-2-Clause", "CMU-Mach-n...")
    ),
    # a List URL with a fragment, as written, and its page: the owners of
    # the page and of each place on it (each read as the bare page's owner)
    **{
        FEDORA_MIT + place: _several("Adobe-Glyph", "MIT-enna", "MIT-feh", "mpich2")
        for place in ("#AdobeGlyph", "#enna", "#feh", "")
    },
    FEDORA_FSFUL + "#License_Retention_Variant": _several("FSFUL", "FSFULLR"),
    FEDORA_FSFUL: _several("FSFUL", "FSFULLR"),
    PYTHON + "#execution-tracing": _several("HPND-SMC", "Python-2.0.1"),
    PYTHON: _several("HPND-SMC", "Python-2.0.1"),
    # a page of a licence and an exception that is no old ID of both
    "https://github.com/maranget/hevea/blob/master/LICENSE": _with(
        "QPL-1.0-INRIA-2004", "QPL-1.0-INRIA-2004-exception"
    ),
    "https://opensource.org/license/wxWindows": _with(
        "wxWindows", "WxWindows-exception-3.1"
    ),
    # a page the List gives one licence that offers a choice (DUAL_PAGES)
    "http://glassfish.java.net/public/CDDL+GPL_1_1.html": _several(*GLASSFISH),
    "https://javaee.github.io/glassfish/LICENSE": _several(*GLASSFISH),
}


@pytest.mark.parametrize(("value", "reason"), REFUSED.items(), ids=list(REFUSED))
def test_a_page_of_no_one_licence_is_refused_with_its_reason(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    got = resolve(value, corpus_db)
    assert _is_unresolved(got)
    assert (got["reason"], got["steps"], got["candidates"]) == (reason, [], [])
    assert got["expansions"] == []


#: The pages the List gives a licence and its variants, read as the licence.
OVERRIDES = {
    "https://www.mozilla.org/MPL/2.0/": "MPL-2.0",
    "https://opensource.org/license/MPL-2.0": "MPL-2.0",
    "https://opensource.org/license/OFL-1.1": "OFL-1.1",
    "http://scripts.sil.org/cms/scripts/page.php?item_id=OFL_web": "OFL-1.1",
}


@pytest.mark.parametrize(("value", "expression"), OVERRIDES.items())
def test_a_page_of_a_licence_and_its_variants_is_the_licence(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, "license_url")
    assert [(s["kind"], s["detail"]) for s in got["steps"]] == [
        ("license_url", "alias")
    ]


@pytest.mark.parametrize("key", URL_ALIASES)
def test_every_alias_reads_as_its_licence(corpus_db: LicenseDatabase, key: str) -> None:
    alias = URL_ALIASES[key]
    got = resolve(f"https://{key}", corpus_db)
    assert got["expression"] == alias.license_id
    assert [(s["kind"], s["detail"]) for s in got["steps"]] == [
        ("license_url", "alias")
    ]
    if alias.license_id == CLASSPATH:
        assert (got["category"], got["trust"]) == ("deprecated_ambiguous", "list_data")
    else:
        assert (got["category"], got["trust"]) == ("license_url", "resolver_rule")


def test_the_old_osi_page_of_the_mit_licence_is_its_alias(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve("http://www.opensource.org/licenses/mit-license.php", corpus_db)
    assert (got["expression"], got["steps"][0]["detail"]) == ("MIT", "alias")


NOT_FOUND = [
    # pages that name no licence
    "https://www.aspose.com/corporate/purchase/end-user-license-agreement.aspx",
    "https://aka.ms/deprecateLicenseUrl",
    "aka.ms/deprecateLicenseUrl",
    "https://go.microsoft.com/fwlink/?LinkId=329770",
    "https://github.com/foo/bar/blob/master/LICENSE",
    "https://huggingface.co/foo/bar/blob/main/LICENSE",
    "https://www.example.com/a/b",
    "www.example.com/a/b",
    # unversioned GNU pages, and a place on a page (a fragment of the List)
    "https://www.gnu.org/licenses/gpl.html",
    "https://www.gnu.org/licenses/lgpl.html",
    "https://www.gnu.org/licenses/gpl-faq.html",
    # a host that is not the one of the page
    "https://spdx.org.evil.com/licenses/MIT.html",
    "https://evil.com/spdx.org/licenses/MIT.html",
    "https://user:pw@spdx.org/licenses/MIT",
    "https://spdx.org@evil.com/licenses/MIT",
    "https://evil.com/licenses/MIT",
    "https://ſpdx.org/licenses/MIT",  # a long s is no ASCII "s"
    # an ID page with more than an ID
    "https://spdx.org/licenses/NotAnId",
    "https://spdx.org/licenses/MIT/extra",
    "https://spdx.org/licenses/MIT?x=1",
    "https://spdx.org/licenses%2FMIT",
    "https://spdx.org%2Flicenses/MIT",
    "https://licenses.nuget.org/MIT%20OR%20Apache-2.0",
    "spdx:NotAnId",
    "spdx:MIT/x",
    "https://scancode-licensedb.aboutcode.org/mit/extra.html",
    # a ScanCode key that is the SPDX ID of another licence
    "https://scancode-licensedb.aboutcode.org/openssl.html",
    "https://scancode-licensedb.aboutcode.org/x11.html",
    # a "+" the List's page reads only after an ID that takes one
    "https://spdx.org/licenses/GPL-2.0-only+",
    "https://spdx.org/licenses/GPL-2.0-or-later+",
    "https://spdx.org/licenses/GPL-2.0++",
    "https://spdx.org/licenses/MIT++",
    "https://spdx.org/licenses/LicenseRef-foo+",
    "https://spdx.org/licenses/Classpath-exception-2.0+",
    "https://spdx.org/licenses/NotAnId+",
    "spdx:MIT+x",
    # and on no other host
    "https://licenses.nuget.org/MIT+",
    "https://choosealicense.com/licenses/mit+/",
    "https://scancode-licensedb.aboutcode.org/mit+.html",
    "https://opensource.org/licenses/MIT+",
    # a port above 65535
    "https://spdx.org:65536/licenses/MIT",
    # prose and a URL: out of scope
    "Apache License https://www.apache.org/licenses/LICENSE-2.0",
    "<https://spdx.org/licenses/MIT",
    "<<https://spdx.org/licenses/MIT>>",
]


@pytest.mark.parametrize("value", NOT_FOUND)
def test_a_url_that_names_nothing_reads_as_nothing(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert _is_unresolved(got)
    assert got["reason"] == f"not found: {reason_detail(value)}"
    assert (got["steps"], got["candidates"], got["expansions"]) == ([], [], [])


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("https://spdx.org/licenses/MIT\x00", "control or format character: U+0000"),
        (
            "https://spdx.org/licenses/M\u200bIT",
            "control or format character: U+200B",
        ),
        ("https://spdx.org/licenses/MIT\udcff", "lone surrogate"),
        ("https://x.org/" + "a" * 2000, "too long: 2014 characters"),
        ("https://spdx.org/licenses/" + "M" * 2000, "too long: 2026 characters"),
    ],
    ids=["nul", "inner-zero-width-space", "surrogate", "long", "long-id"],
)
def test_the_gates_of_resolve_come_first(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    got = resolve(value, corpus_db)
    assert _is_unresolved(got)
    assert got["reason"] == reason
    assert got["steps"] == []


#: ``{value: (expression, category, reason)}``
OPERANDS = {
    "https://spdx.org/licenses/MIT OR Apache-2.0": ("Apache-2.0 OR MIT", "license_url"),
    "MIT OR " + APACHE_URL: ("Apache-2.0 OR MIT", "license_url"),
    f"MIT OR ({APACHE_URL})": ("Apache-2.0 OR MIT", "license_url"),
    "https://spdx.org/licenses/MIT OR https://spdx.org/licenses/Apache-2.0": (
        "Apache-2.0 OR MIT",
        "license_url",
    ),
    "(https://spdx.org/licenses/MIT OR https://spdx.org/licenses/ISC)": (
        "ISC OR MIT",
        "license_url",
    ),
    "https://www.gnu.org/licenses/gpl-3.0.html OR MIT": (
        "GPL-3.0 OR MIT",
        "assumed_only",
    ),
}


@pytest.mark.parametrize(("value", "expected"), OPERANDS.items(), ids=list(OPERANDS))
def test_a_url_is_an_operand_of_an_expression(
    corpus_db: LicenseDatabase, value: str, expected: tuple[str, str]
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (*expected, None)
    kinds = {s["kind"] for o in got["operands"] for s in o["steps"]}
    assert "license_url" in kinds


UNREAD = {
    "MIT OR https://www.unicode.org/license.txt": _several(
        "Unicode-3.0", "Unicode-DFS-2016"
    ),
    "MIT OR https://spdx.org/licenses/Classpath-exception-2.0": _exception(
        "Classpath-exception-2.0"
    ),
    "MIT OR https://www.example.com/a/b": (
        "operand not resolved: https://www.example.com/a/b"
    ),
    "MIT OR www.example.com/a/b": "operand not resolved: www.example.com/a/b",
    # Licences joined by ";" have no operator, and say so when each part is
    # read; with a part that is not, the whole is not found.
    "MIT; " + APACHE_URL: "operator not stated: ;",
    f"https://spdx.org/licenses/MIT;{APACHE_URL}": "operator not stated: ;",
    "MIT; https://www.example.com/a/b": "not found: MIT; https://www.example.com/a/b",
    "MIT; https://www.unicode.org/license.txt": (
        "not found: MIT; https://www.unicode.org/license.txt"
    ),
    # A "/" joins no URL to an ID.
    "MIT/" + APACHE_URL: f"not found: MIT/{APACHE_URL}",
    APACHE_URL + "/MIT": f"not found: {APACHE_URL}/MIT",
}


@pytest.mark.parametrize(("value", "reason"), UNREAD.items(), ids=list(UNREAD))
def test_a_url_that_cannot_be_read_refuses_its_expression(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == reason
