# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads the licence expression in the path of a
``licenses.nuget.org`` URL (``licenseid.nugetpath``, issue #187).

Read on the database of the whole 3.29.0 List (``corpus_db``). Each table of
refusals has a positive control: the same shape, one character from an
answer, so that an empty database cannot pass it.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from test_url_markers import tag_answer

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.errors import reason_detail
from licenseid.nugetpath import decode, decoded_path
from licenseid.resolvereason import names_expression
from licenseid.resolveurl import url_license_id
from licenseid.urlkey import url_key

NUGET = "https://licenses.nuget.org/"
CONTROL = NUGET + "MIT%20OR%20ISC"
DEPTH = 151  # one over identifiers.MAX_PARSE_DEPTH and MAX_PARSE_OPERATORS


def _reads(db: LicenseDatabase) -> None:
    """The control: the database reads a compound URL (not a vacuous test)."""
    assert resolve(CONTROL, db)["expression"] == "ISC OR MIT"


@pytest.mark.parametrize(
    ("raw", "decoded"),
    [
        ("MIT%20OR%20ISC", "MIT OR ISC"),
        ("%28MIT%29", "(MIT)"),
        ("%4d%49%54", "MIT"),  # either hex case
        ("%2520", "%20"),  # once: the result is not decoded again
        ("%2B%2b", "++"),
        ("MIT", "MIT"),
        ("%C2%A0", "\xc2\xa0"),  # bytes, not UTF-8
        ("%zz", "%zz"),  # not an escape
        ("%2", "%2"),
    ],
)
def test_decode_replaces_every_escape_once(raw: str, decoded: str) -> None:
    assert decode(raw) == decoded


def _path(url: str) -> str | None:
    key = url_key(url)
    return None if key is None else decoded_path(url, key)


@pytest.mark.parametrize(
    ("url", "path"),
    [
        (CONTROL, "MIT OR ISC"),
        ("licenses.nuget.org/(MIT)", "(MIT)"),
        ("HTTP://WWW.Licenses.NuGet.org:443/MIT%20OR%20ISC/", "MIT OR ISC"),
        (CONTROL + "#frag", "MIT OR ISC"),
        # the key dropped more than case, or a character is outside the set
        (CONTROL + ".txt", None),
        (CONTROL + "?x=1", None),
        (NUGET, None),
        (NUGET + "MIT/ISC", None),
        (NUGET + "MIT%2FISC", None),
        (NUGET + "MIT%20%20ISC", None),
        (NUGET + "%20MIT", None),
        (NUGET + "MIT%20", None),
        ("https://spdx.org/licenses/MIT%20OR%20ISC", None),
        ("https://evil.com/licenses.nuget.org/MIT", None),
    ],
)
def test_the_path_is_decoded_for_this_host_only(url: str, path: str | None) -> None:
    assert _path(url) == path


POSITIVE = {
    # The examples of the issue.
    NUGET + "MIT": "MIT",
    NUGET + "(MIT)": "MIT",
    NUGET + "(Apache-2.0+)": "Apache-2.0+",
    NUGET + "(LGPL-2.0-only%20WITH%20FLTK-exception%20OR%20Apache-2.0+)": (
        "Apache-2.0+ OR LGPL-2.0-only WITH FLTK-exception"
    ),
    "licenses.nuget.org/MIT%20OR%20Apache-2.0": "Apache-2.0 OR MIT",
    NUGET + "(MIT)%20OR%20ISC": "ISC OR MIT",  # a live page
    # Operators, brackets, "+", and every spelling of an escape.
    NUGET + "MS-PL%20OR%20Apache-2.0": "Apache-2.0 OR MS-PL",
    NUGET + "MIT%20AND%20(ISC%20OR%20Zlib)": "MIT AND (ISC OR Zlib)",
    NUGET + "(MIT)%20AND%20(ISC%20OR%20Zlib)": "MIT AND (ISC OR Zlib)",
    NUGET + "((MIT))": "MIT",
    NUGET + "((MIT)%20OR%20(ISC))": "ISC OR MIT",  # resolve() strips the outer
    NUGET + "Apache-2.0+%20OR%20MIT": "Apache-2.0+ OR MIT",
    NUGET + "MIT%2B": "MIT+",
    NUGET + "MIT%20%4F%52%20ISC": "ISC OR MIT",  # an escaped upper-case OR
    NUGET + "%28MIT%29%20OR%20%28ISC%29": "ISC OR MIT",
    NUGET + "%4D%49%54": "MIT",  # harmless: it is an M, an I and a T
    NUGET + "%4d%49%54%20OR%20isc": "ISC OR MIT",
    NUGET + "mit%20OR%20isc": "ISC OR MIT",  # IDs fold case as they do alone
    NUGET + "MIT%20OR%20MIT": "MIT",
    NUGET + "GPL-2.0-only%20WITH%20Classpath-exception-2.0": (
        "GPL-2.0-only WITH Classpath-exception-2.0"
    ),
    NUGET + "GPL-3.0%20OR%20MIT": "GPL-3.0 OR MIT",  # assumed_only
    NUGET + "MIT.": "MIT",
    NUGET + "MIT?": "MIT",  # an empty query is no query, as the key has it
    NUGET + "(MIT)%20OR%20ISC?": "ISC OR MIT",
    # What a value is wrapped in, and spellings of one page.
    f"<{CONTROL}>": "ISC OR MIT",
    f"({CONTROL})": "ISC OR MIT",
    f'"{CONTROL}"': "ISC OR MIT",
    CONTROL + ".": "ISC OR MIT",
    CONTROL + "/": "ISC OR MIT",
    CONTROL + "#x": "ISC OR MIT",
    CONTROL.replace("https", "http"): "ISC OR MIT",
    CONTROL.removeprefix("https://"): "ISC OR MIT",
    f"  {CONTROL}\n": "ISC OR MIT",
    # The page with raw spaces, as before.
    NUGET + "MIT OR ISC": "ISC OR MIT",
}


@pytest.mark.parametrize(
    ("value", "expression"), POSITIVE.items(), ids=[v[:80] for v in POSITIVE]
)
def test_an_expression_url_reads_as_its_expression(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == expression
    assert got["reason"] is None
    assert got["category"] in ("license_url", "assumed_only", "lexical")
    # the decoded text has the same steps alone, after the lead
    lead_at = [i for i, s in enumerate(got["steps"]) if s["kind"] == "license_url"]
    if lead_at and got["steps"][lead_at[0]]["detail"] == "expression in path":
        lead = got["steps"][lead_at[0]]
        alone = resolve(lead["to"], corpus_db)
        assert alone["expression"] == expression
        assert got["steps"][lead_at[0] + 1 :] == alone["steps"]
    # the fixed point: the answer reads as itself
    assert resolve(expression, corpus_db)["expression"] == expression


@pytest.mark.parametrize("value", [CONTROL, NUGET + "(MIT)", NUGET + "MIT"])
def test_one_url_is_one_operand(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(f"  {value} ", corpus_db)
    (operand,) = got["operands"]
    start, end = operand["span"]
    assert f"  {value} "[start:end] == operand["text"] == value
    assert operand["expression"] == got["expression"]
    alone = resolve(value, corpus_db)["operands"]
    assert alone == [{**operand, "span": [0, len(value)]}]


def test_the_steps_lead_from_the_url_to_the_expression(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve(NUGET + "(MIT)%20OR%20ISC", corpus_db)
    assert [(s["kind"], s["from"], s["to"]) for s in got["steps"]] == [
        ("license_url", NUGET + "(MIT)%20OR%20ISC", "(MIT) OR ISC"),
        ("brackets", "(MIT) OR ISC", "MIT OR ISC"),
        ("reorder", "MIT OR ISC", "ISC OR MIT"),
    ]
    assert (got["category"], got["trust"]) == ("license_url", "resolver_rule")
    wrapped = resolve(f"<{CONTROL}>", corpus_db)
    assert [s["kind"] for s in wrapped["steps"]] == [
        "brackets",
        "license_url",
        "reorder",
    ]


def test_a_bare_deprecated_id_stays_assumed(corpus_db: LicenseDatabase) -> None:
    got = resolve(NUGET + "GPL-3.0%20OR%20MIT", corpus_db)
    assert (got["category"], got["trust"]) == ("assumed_only", "none")
    assert [e["kind"] for e in got["expansions"]] == ["assumed_only"]


# --- the ID pages keep their answers ---


@pytest.mark.parametrize(
    ("value", "expression", "detail"),
    [
        (NUGET + "MIT", "MIT", "id in path"),
        (NUGET + "mit", "MIT", "id in path"),
        (NUGET + "GPL-2.0+", "GPL-2.0-or-later", "id in path"),
        (NUGET + "MIT+", "MIT+", "expression in path"),
    ],
)
def test_a_single_id_is_read_as_before(
    corpus_db: LicenseDatabase, value: str, expression: str, detail: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == expression
    assert got["steps"][0]["detail"] == detail


def test_an_exception_page_is_refused_as_before(corpus_db: LicenseDatabase) -> None:
    got = resolve(NUGET + "FLTK-exception", corpus_db)
    assert (got["expression"], got["reason"]) == (
        None,
        "url names an exception: FLTK-exception",
    )


# --- refusals: the grammar and the leaf reader say why ---

REFUSED = {
    NUGET + "(MIT": ("malformed", "(MIT"),
    NUGET + "MIT%20OR": ("malformed", "MIT OR"),
    NUGET + "MIT%20OR%20(ISC": ("malformed", "MIT OR (ISC"),
    NUGET + "GPL-2.0-only+": ("malformed", "GPL-2.0-only+"),
    NUGET + "GPL-2.0-only+%20OR%20MIT": ("malformed", "GPL-2.0-only+ OR MIT"),
    NUGET + "(" * DEPTH + "MIT%20OR%20ISC" + ")" * DEPTH + "%20OR%20Zlib": (
        "unresolved",
        "(" * DEPTH + "MIT OR ISC" + ")" * DEPTH + " OR Zlib",
    ),
    NUGET + "%20OR%20".join(["MIT"] * (DEPTH + 1)): (
        "unresolved",
        " OR ".join(["MIT"] * (DEPTH + 1)),
    ),
}


@pytest.mark.parametrize(("value", "refusal"), REFUSED.items(), ids=range(len(REFUSED)))
def test_a_refused_expression_gives_the_reason_it_has_alone(
    corpus_db: LicenseDatabase, value: str, refusal: tuple[str, str]
) -> None:
    _reads(corpus_db)
    category, decoded = refusal
    got = resolve(value, corpus_db)
    alone = resolve(decoded, corpus_db)
    assert got["expression"] is None
    assert got["category"] == category
    assert got["reason"] == alone["reason"]
    assert got["reason"] is not None
    assert not got["reason"].startswith("not found")
    assert got["steps"] == []  # as a refusal of any other page has none
    wrapped = resolve(f"<{value}>", corpus_db)
    assert (wrapped["reason"], wrapped["steps"]) == (got["reason"], [])


# --- not found: nothing in it is an answer ---

_OPERAND = "%20OR%20ISC"
NOT_FOUND = [
    # operators in upper case only
    "MIT%20or%20ISC",
    "MIT%20Or%20ISC",
    "MIT%20%6F%72%20ISC",  # an escape does not change case: "or"
    "MIT%20%4F%72%20ISC",
    "MIT%20and%20ISC",
    "MIT%20OR%20ISC%20and%20Zlib",
    "GPL-2.0-only%20with%20Classpath-exception-2.0",
    # words that are no licence of the List
    "UNLICENSED",
    "LicenseRef-x",
    "LicenseRef-x%20OR%20MIT",
    "MIT%20WITH%20AdditionRef-x",
    "Foo",
    # a loose spelling resolve() reads alone: NuGet serves SPDX IDs only
    "Apache2",
    "GPLv3",
    "GPL2%20OR%20MIT",
    "LGPLv2.1+%20OR%20MIT",
    "MIT-%20OR%20ISC",
    "MIT.%20OR%20ISC.",
    "MIT%20OR%20ISC%2E",
    "Classpath-exception-2.0%20OR%20MIT",
    "MIT%20WITH%20Foo",
    "Foo%20WITH%20Classpath-exception-2.0",
    "MIT%20OR%20Foo",
    "Apache-2.0%20or%20later",
    "MIT%20+",
    "NONE",
    # a "+" is not a space, and an escape outside the set is not read
    "MIT+OR+ISC",
    "MIT%2FISC",
    "MIT%3FISC",
    "MIT%23ISC",
    "MIT%3BISC",
    "MIT%00" + _OPERAND,
    "MIT%0A" + _OPERAND,
    "MIT%09OR%20ISC",
    "MIT%7F" + _OPERAND,
    "MIT%C2%A0OR%20ISC",
    "MIT%22" + _OPERAND,
    "%5BMIT%5D" + _OPERAND,
    "%7BMIT%7D" + _OPERAND,
    "MIT%2520OR%2520ISC",  # doubled: decoded once, a "%" is left
    "MIT%25" + _OPERAND,
    # spaces: one between words, none at the ends
    "MIT%20%20OR%20ISC",
    "%20MIT" + _OPERAND,
    "MIT" + _OPERAND + "%20",
    "%20",
    "(MIT)%20(ISC)",
    "MIT%20ISC",
    "OR",
    "AND",
    "()",
    "",
    # the page is not the last segment as written
    "MIT%20OR%20ISC?x=1",
    "MIT%20OR%20ISC.txt",
    "MIT%20OR%20ISC.html",
    "MIT%20OR%20ISC/extra",
    "(MIT) OR ISC",  # raw spaces in a bracket path
]


@pytest.mark.parametrize("path", NOT_FOUND)
def test_a_path_that_is_no_expression_is_not_found(
    corpus_db: LicenseDatabase, path: str
) -> None:
    _reads(corpus_db)
    value = NUGET + path
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"not found: {reason_detail(value)}"
    assert (got["steps"], got["candidates"], got["expansions"]) == ([], [], [])


def test_a_url_over_the_gate_is_not_found(corpus_db: LicenseDatabase) -> None:
    _reads(corpus_db)
    under = NUGET + "MIT%20OR%20" * 150 + "ISC"
    over = NUGET + "MIT%20OR%20" * 190 + "ISC"
    assert len(under) < 2048 < len(over)  # the key refuses a URL over 2,048
    assert resolve(under, corpus_db)["expression"] == "ISC OR MIT"
    assert resolve(over, corpus_db)["reason"] is not None
    assert resolve(over, corpus_db)["expression"] is None


# --- as an operand of a compound ---

COMPOUND_OF_URLS = {
    NUGET + "MIT OR " + NUGET + "ISC": "ISC OR MIT",
    NUGET + "MIT AND " + NUGET + "ISC": "ISC AND MIT",
    "ISC AND " + NUGET + "MIT": "ISC AND MIT",
    NUGET + "MIT OR Zlib": "MIT OR Zlib",
}


@pytest.mark.parametrize(("value", "expression"), COMPOUND_OF_URLS.items())
def test_urls_that_name_one_licence_join_as_operands(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == expression


@pytest.mark.parametrize(
    "value",
    [
        "ISC AND " + CONTROL,
        CONTROL + " OR Zlib",
        CONTROL + " OR " + NUGET + "Zlib",
        "Zlib AND (" + CONTROL + ")",
    ],
)
def test_a_url_of_an_expression_is_no_operand(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == names_expression(CONTROL)


# --- the same reader for a tag, a field and the commands ---


def test_a_bracketed_compound_keeps_its_precedence_in_a_tag(
    corpus_db: LicenseDatabase,
) -> None:
    assert tag_answer(corpus_db, CONTROL) == "ISC OR MIT"
    assert tag_answer(corpus_db, "Zlib AND " + CONTROL) == "Zlib AND (ISC OR MIT)"


def _cli(db: LicenseDatabase, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, ["--db", db.location, *args])
    return result.exit_code, result.stdout, result.stderr


def test_the_commands_read_the_expression_resolve_reads(
    corpus_db: LicenseDatabase,
) -> None:
    for command in ("resolve", "detect"):
        code, out, err = _cli(corpus_db, command, CONTROL)
        assert (code, err) == (0, "")
        assert out.startswith("EXPRESSION=ISC OR MIT\t")
    assert _cli(corpus_db, "is-osi", CONTROL) == _cli(corpus_db, "is-osi", "ISC OR MIT")
    code, out, _ = _cli(corpus_db, "detect", "--id", CONTROL)  # one licence only
    assert (code, out) == (2, "")


@pytest.mark.terse_cli
def test_the_terse_output_is_the_expression_alone(corpus_db: LicenseDatabase) -> None:
    assert _cli(corpus_db, "resolve", NUGET + "(MIT)")[1] == "MIT\n"


def test_a_refusal_has_no_step_of_its_wrapper(corpus_db: LicenseDatabase) -> None:
    _reads(corpus_db)
    got = resolve(f"<{NUGET}MIT%20OR>", corpus_db)
    assert (got["category"], got["steps"]) == ("malformed", [])
    assert resolve(f"<{CONTROL}>", corpus_db)["steps"][0]["kind"] == "brackets"


@pytest.mark.parametrize(
    ("path", "candidates"),
    [
        ("(GPL-3.0)", ["GPL-3.0-only", "GPL-3.0-or-later"]),
        ("(AGPL-1.0)", ["AGPL-1.0-only", "AGPL-1.0-or-later"]),
        (
            "GPL-2.0%20WITH%20Classpath-exception-2.0",
            [
                "GPL-2.0-only WITH Classpath-exception-2.0",
                "GPL-2.0-or-later WITH Classpath-exception-2.0",
            ],
        ),
        ("MIT", []),
    ],
)
def test_one_licence_keeps_what_it_has_alone(
    corpus_db: LicenseDatabase, path: str, candidates: list[str]
) -> None:
    got = resolve(NUGET + path, corpus_db)
    alone = resolve(got["steps"][0]["to"], corpus_db)
    assert got["candidates"] == candidates == alone["candidates"]
    assert got["category"] != "unresolved"


def test_an_and_expression_is_no_operand_either(corpus_db: LicenseDatabase) -> None:
    url = NUGET + "MIT%20AND%20ISC"
    got = resolve("Zlib OR " + url, corpus_db)
    assert (got["expression"], got["reason"]) == (None, names_expression(url))
    with corpus_db.reading():
        assert url_license_id(corpus_db, url) == "(ISC AND MIT)"


def test_a_leaf_the_reader_cannot_read_is_not_found(
    corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defence in depth: the check of the IDs and the leaf reader agree."""
    _reads(corpus_db)
    monkeypatch.setattr("licenseid.nugetpath.read_leaf", lambda *_: False)
    got = resolve(CONTROL, corpus_db)
    assert got["reason"] == f"not found: {reason_detail(CONTROL)}"


@pytest.mark.parametrize(
    "value",
    [
        CONTROL + " or later",
        "(MIT OR ISC) or later",
        "(MIT AND ISC) or later",
        "((MIT) OR ISC) or later",
        "(MIT OR (ISC)) or later",
        "(GPL-2.0+ OR MIT) or later",
    ],
)
def test_a_tag_gives_no_answer_to_an_or_later_after_a_compound_group(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A grant after a bracketed group of several licences is whose? Like
    resolve(), the tag answers nothing, not the last leaf's "+"."""
    assert resolve(value, corpus_db)["expression"] is None
    assert tag_answer(corpus_db, value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("(GPL-2.0) or later", "GPL-2.0-or-later"),
        ("MIT OR (GPL-2.0) or later", "GPL-2.0-or-later OR MIT"),
        ("(MIT OR ISC or later)", "MIT OR ISC+"),
        ("MIT OR GPL-2.0 or later", "GPL-2.0-or-later OR MIT"),
    ],
)
def test_a_tag_keeps_an_or_later_that_has_one_licence(
    corpus_db: LicenseDatabase, value: str, expected: str
) -> None:
    """Positive controls: a grant beside one licence (in brackets or not)
    still qualifies it."""
    assert tag_answer(corpus_db, value) == expected
