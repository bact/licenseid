# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The user docs name what the code has: each option of each command, each
step kind, step detail and refusal reason ``resolve()`` gives, each key of
its result and of ``detect()``'s, the categories, the numbers the prose
states, and links that resolve (roadmap item 57)."""
# pylint: disable=missing-function-docstring

import re
import typing
from collections.abc import Mapping
from pathlib import Path

import click
import pytest
from docs_blocks import (
    BLOB,
    DOCS,
    README,
    ROOT,
    code_spans,
    folded,
    links,
    name_of,
    pages,
    section,
    slugs,
    table,
    text_of,
    unticked,
)
from docs_reasons import REASON_EXAMPLES
from resolver_corpus import FIXTURES, read_rows

from licenseid import LicenseDatabase, resolve, resolvertypes
from licenseid.cli import cli
from licenseid.result import no_detection_line
from licenseid.types import Detection
from licenseid.variants import VARIANTS
from tools.pypi_licence_sample.answer import unescape_field

CLI = DOCS / "cli.md"
_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
RESOLVE = DOCS / "resolve.md"
RESOLVE_VALUES = DOCS / "resolve-values.md"
#: The section of docs/cli.md that documents each command. "Common options"
#: (under detect's heading) serve detect and the is-* commands too.
SECTIONS = {
    "update": "## Update the licence database",
    "detect": "## Detect a licence, or resolve a declared value",
    "resolve": "## Resolve a declared value",
    "clear-cache": "## Cache management",
    "is-osi": "## Licence predicates",
    "is-fsf": "## Licence predicates",
    "is-spdx": "## Licence predicates",
}
COMMON = "## Detect a licence, or resolve a declared value"
#: Choices a command checks itself, not through click.Choice.
CHOICES = {("detect", "variant"): VARIANTS}


def _documented(text: str) -> tuple[set[str], set[str]]:
    """The option forms (``--cache``, ``--no-cache`` of ``--cache/--no-cache``)
    and the words (choices too: ``--source auto|database``) in the code spans
    of *text*."""
    spans = code_spans(text)
    forms = {
        f for s in spans for f in re.findall(r"(?<![\w-])(-{1,2}[A-Za-z][\w-]*)", s)
    }
    words = {w for s in spans for w in re.split(r"[\s|/,]+", s)}
    return forms, words


def _missing(name: str, command: click.Command) -> list[str]:
    text = section(CLI, SECTIONS[name])
    if name.startswith("is-"):
        text += section(CLI, COMMON)
    forms, words = _documented(text)
    missing = []
    for param in command.params:
        if not isinstance(param, click.Option) or param.hidden:
            continue
        missing += [f for f in [*param.opts, *param.secondary_opts] if f not in forms]
        choices: tuple[str, ...] = CHOICES.get((name, str(param.name)), ())
        if isinstance(param.type, click.Choice):
            choices = tuple(str(c) for c in param.type.choices)
        missing += [f"--{param.name} {c}" for c in choices if c not in words]
    return missing


@pytest.mark.parametrize("name", sorted(SECTIONS))
def test_each_option_is_in_the_section_of_its_command(name: str) -> None:
    missing = _missing(name, cli.commands[name])
    assert not missing, f"docs/cli.md: {name} {missing} not in {SECTIONS[name]!r}"


def test_each_command_has_a_section() -> None:
    assert set(cli.commands) == set(SECTIONS)


def test_the_global_options_are_documented() -> None:
    forms, _ = _documented(text_of(CLI))
    missing = [f for p in cli.params for f in p.opts if f not in forms]
    assert not missing, f"docs/cli.md: global options {missing} not documented"


WORKED_ROWS = table(section(DOCS / "resolve-flow.md", "## Worked examples"), "Value")


@pytest.fixture(name="corpus", scope="module")
def _corpus(bundle_db: LicenseDatabase) -> list[resolvertypes.Resolution]:
    """``resolve()`` of every value of the resolver fixtures (627 values), the
    worked examples of resolve-flow.md and the examples of the step-detail
    table of resolve.md."""
    values = {
        unescape_field(row["value"])
        for path in sorted(FIXTURES.glob("*.tsv"))
        for row in read_rows(path)
    }
    values |= {unticked(r["Value"]) for r in WORKED_ROWS}
    values |= {e for pairs in _detail_rows().values() for _, e in pairs}
    return [resolve(value, bundle_db) for value in sorted(values)]


def _parts(
    corpus: list[resolvertypes.Resolution],
) -> list[Mapping[str, typing.Any]]:
    """Each result and each of its operands."""
    out: list[Mapping[str, typing.Any]] = []
    for result in corpus:
        out += [result, *result["operands"]]
    return out


def _steps(part: Mapping[str, typing.Any]) -> list[dict[str, typing.Any]]:
    return [s for s in [*part["steps"], *part["expansions"]] if isinstance(s, dict)]


def test_each_step_kind_is_documented(corpus: list[resolvertypes.Resolution]) -> None:
    kinds = {s["kind"] for p in _parts(corpus) for s in _steps(p)}
    kinds |= set(resolvertypes.LEXICAL_KINDS) | set(resolvertypes.LIST_PROVIDES)
    # A step kind is named on the page that reads it: either of the two.
    spans = set(code_spans(text_of(RESOLVE)))
    spans |= set(code_spans(text_of(RESOLVE_VALUES)))
    assert not kinds - spans, f"docs/resolve*.md: step kinds {kinds - spans} not named"


def _detail_rows() -> dict[str, list[tuple[str, str]]]:
    """``kind: [(detail, example)]`` of the step-detail table of resolve.md:
    the n-th detail of a row is given by its n-th example. An invisible
    character is written as ``\\uXXXX`` (a bidi control turns the page
    around), decoded here."""
    rows = table(section(RESOLVE, "## The whole result"), "Step kind")
    out = {}
    for row in rows:
        details = re.findall(r"`([^`]*)`", row["`detail`"])
        examples = [
            _UNICODE_ESCAPE.sub(lambda m: chr(int(m[1], 16)), e)
            for e in re.findall(r"`([^`]*)`", row["Example value"])
        ]
        out[row["Step kind"].strip("`")] = list(zip(details, examples))
    return out


def test_each_step_kind_of_the_table_is_one_the_code_has() -> None:
    """The reverse: a kind the detail table names the code no longer has."""
    code = (
        set(resolvertypes.LEXICAL_KINDS)
        | set(resolvertypes.LIST_PROVIDES)
        | set(resolvertypes.CATEGORY_ORDER)  # prose_form rests on no list
    )
    stale = set(_detail_rows()) - code - {"drop"}
    assert not stale, f"docs/resolve.md: step kinds {stale} are not in the code"
    flow = section(DOCS / "resolve-flow.md", "## Step kinds, categories and trust")
    given = table(flow, "Category (strong to weak)")[1]["Given by"]
    assert set(re.findall(r"`(\w+)`", given)) <= code


#: The conditions of a reason that are no colon form in docs/resolve.md.
BARE_CONDITIONS = (
    "empty",
    "lone surrogate",
    "mismatched brackets",
    "too many operators",
    "too deeply nested",
)


def test_each_reason_the_docs_list_is_one_resolve_gives(
    bundle_db: LicenseDatabase, corpus: list[resolvertypes.Resolution]
) -> None:
    """A condition of "Reasons for a refusal" (the lower-case words before a
    colon in a code span, and the bare ones above) is the reason of a value
    of the corpus or of ``REASON_EXAMPLES``, so a reason the code renamed or
    dropped fails here."""
    spans = code_spans(section(RESOLVE, "## Reasons for a refusal"))
    listed = {
        s.partition(":")[0]
        for s in spans
        if ":" in s and re.fullmatch(r"[a-z][a-z ]+", s.partition(":")[0])
    } | set(BARE_CONDITIONS)
    given = {p["reason"].partition(":")[0] for p in _parts(corpus) if p["reason"]}
    for condition, value in REASON_EXAMPLES.items():
        reason = str(resolve(value, bundle_db)["reason"])
        assert reason.partition(":")[0] == condition, f"{value[:30]!r}: {reason}"
        assert condition in listed, f"docs/resolve.md: reason {condition!r} missing"
        given.add(condition)
    gone = sorted(listed - given)
    assert len(listed) >= 20
    assert not gone, f"docs/resolve.md: reasons {gone} are not given by resolve()"


def test_each_detail_the_corpus_gives_is_in_the_table(
    corpus: list[resolvertypes.Resolution],
) -> None:
    rows = _detail_rows()
    given = {
        (s["kind"], s["detail"])
        for p in _parts(corpus)
        for s in _steps(p)
        if s["detail"] is not None and s["kind"] != "drop"
    }
    shown = {(kind, d) for kind, pairs in rows.items() for d, _ in pairs}
    assert not given - shown, f"docs/resolve.md: step details {given - shown} missing"
    drops = {
        s["detail"] for p in _parts(corpus) for s in _steps(p) if s["kind"] == "drop"
    }
    assert drops and all(
        re.fullmatch(r"U\+[0-9A-F]{4,6}( U\+[0-9A-F]{4,6})*", d) for d in drops
    )


@pytest.mark.parametrize(
    ("kind", "detail", "example"),
    [(k, d, e) for k, pairs in _detail_rows().items() if k != "drop" for d, e in pairs],
)
def test_each_detail_in_the_table_is_what_its_example_gives(
    bundle_db: LicenseDatabase, kind: str, detail: str, example: str
) -> None:
    got = [(s["kind"], s["detail"]) for s in _steps(resolve(example, bundle_db))]
    assert (kind, detail) in got, f"docs/resolve.md: {example!r} gives {got}"


def test_each_detail_has_its_example() -> None:
    """One example per detail (``drop``'s detail is the code points of its
    example's mark)."""
    rows = table(section(RESOLVE, "## The whole result"), "Step kind")
    for row in rows:
        if row["Step kind"] == "`drop`":
            continue
        details = re.findall(r"`([^`]*)`", row["`detail`"])
        examples = re.findall(r"`([^`]*)`", row["Example value"])
        assert len(details) == len(examples), f"docs/resolve.md: {row['Step kind']}"


def test_each_reason_condition_is_documented(
    corpus: list[resolvertypes.Resolution],
) -> None:
    conditions = {p["reason"].split(":")[0] for p in _parts(corpus) if p["reason"]}
    text = folded(section(RESOLVE, "## Reasons for a refusal"))
    missing = sorted(c for c in conditions if c not in text)
    assert len(conditions) >= 10
    assert not missing, f"docs/resolve.md: reasons {missing} not under the heading"


@pytest.mark.parametrize(
    ("kind", "page"),
    [
        (resolvertypes.Resolution, RESOLVE),
        (resolvertypes.Operand, RESOLVE),
        (resolvertypes.ListInfo, RESOLVE),
        (resolvertypes.ToolInfo, RESOLVE),
        (Detection, DOCS / "python-api.md"),
    ],
    ids=lambda x: getattr(x, "__name__", None) or getattr(x, "name", ""),
)
def test_each_key_of_a_result_is_documented(kind: type, page: Path) -> None:
    spans = set(code_spans(text_of(page)))
    missing = sorted(set(typing.get_type_hints(kind)) - spans)
    assert not missing, f"{name_of(page)}: keys of {kind.__name__} {missing} missing"


def test_each_field_of_the_detect_record_is_documented() -> None:
    keys = [field.partition("=")[0] for field in no_detection_line("x").split("\t")]
    spans = set(code_spans(section(DOCS / "output.md", "## Default and verbose text")))
    missing = [k for k in keys if k not in spans]
    assert not missing, f"docs/output.md: record fields {missing} missing"


def test_the_category_table_of_resolve_flow_is_the_code() -> None:
    text = section(DOCS / "resolve-flow.md", "## Step kinds, categories and trust")
    rows = table(text, "Category (strong to weak)")
    got = [(r["Category (strong to weak)"].strip("`"), r["Trust"]) for r in rows]
    want = [(c, resolvertypes.TRUST[c]) for c in resolvertypes.CATEGORY_ORDER]
    assert got == want, "docs/resolve-flow.md: the category table is not CATEGORY_ORDER"
    lexical = set(re.findall(r"`(\w+)`", rows[1]["Given by"]))
    assert lexical == set(resolvertypes.LEXICAL_KINDS), "docs/resolve-flow.md: lexical"


def test_the_readme_links_every_page_of_the_docs() -> None:
    targets = {target for _, target in links(README)}
    missing = [
        name_of(p)
        for p in sorted(DOCS.glob("*.md"))
        if BLOB + name_of(p) not in targets
    ]
    assert not missing, f"README.md does not link {missing}"


def _broken(page: Path) -> list[str]:
    bad = []
    for line, target in links(page):
        url = target.replace(BLOB, "") if target.startswith(BLOB) else target
        if re.match(r"[a-z]+:", url):
            continue
        path, _, anchor = url.partition("#")
        base = ROOT if target.startswith(BLOB) else page.parent
        file = (base / path).resolve() if path else page
        unknown = anchor and file.suffix == ".md" and anchor not in slugs(file)
        if not file.exists() or unknown:
            bad.append(f"{name_of(page)}:{line}: {target}")
    return bad


@pytest.mark.parametrize("page", pages(), ids=name_of)
def test_each_relative_link_and_anchor_resolves(page: Path) -> None:
    assert not _broken(page), f"broken links: {_broken(page)}"
