# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Readers of the user docs (``docs/*.md`` and ``README.md``) for the doc
tests (``tests/test_docs_*.py``): sections, tables, code spans, links and the
fenced blocks with their ``<!-- docs-example: ... -->`` markers. Plain
helpers, no tests."""

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).parents[1]
DOCS: Final = ROOT / "docs"
README: Final = ROOT / "README.md"
#: README links into the docs by absolute URL (it is the PyPI page).
BLOB: Final = "https://github.com/bact/licenseid/blob/main/"

_FENCE: Final = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
_HEADING: Final = re.compile(r"^(#{1,6}) (.*)$")
_MARKER: Final = re.compile(r"^<!-- docs-example: (.+) -->$")
_SPAN: Final = re.compile(r"`([^`]+)`")
_LINK: Final = re.compile(r"\]\(([^)\s]+)\)|^\[[^\]]+\]: (\S+)", re.MULTILINE)


def pages() -> list[Path]:
    """Every page of the user docs: ``docs/*.md``, then ``README.md``."""
    return [*sorted(DOCS.glob("*.md")), README]


def name_of(path: Path) -> str:
    """*path* as the doc tests name it: ``docs/cli.md``, ``README.md``."""
    return path.relative_to(ROOT).as_posix()


@cache
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def text_of(path: Path) -> str:
    """The text of a page (read once per process)."""
    return _read(path)


def prose_lines(text: str) -> list[tuple[int, str]]:
    """``(line number, line)`` of each line outside a fenced block."""
    out, fence = [], ""
    for number, line in enumerate(text.splitlines(), 1):
        found = _FENCE.match(line)
        if found and (not fence or found.group(1).startswith(fence)):
            fence = "" if fence else found.group(1)
            continue
        if not fence:
            out.append((number, line))
    return out


def section(path: Path, heading: str) -> str:
    """The text under *heading* (a whole line, ``## Licence predicates``) up
    to the next heading of its level or above; a heading the page lacks
    fails, naming it, so a renamed heading fails loudly."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text_of(path).splitlines()
    start = None
    for number, line in prose_lines(text_of(path)):
        if start is None:
            start = number if line == heading else None
            continue
        found = _HEADING.match(line)
        if found and len(found.group(1)) <= level:
            return "\n".join(lines[start : number - 1])
    if start is None:
        raise LookupError(f"{name_of(path)}: no heading {heading!r}")
    return "\n".join(lines[start:])


def folded(text: str) -> str:
    """*text* with each run of white space as one space, as Markdown shows a
    paragraph: a phrase broken over two lines is found whole."""
    return " ".join(text.split())


def code_spans(text: str) -> list[str]:
    """The inline code of the prose of *text* (folded, so a span may cross a
    line; fenced blocks left out)."""
    return _SPAN.findall(folded("\n".join(line for _, line in prose_lines(text))))


def cells(line: str) -> list[str]:
    """The cells of one table row, stripped; ``\\|`` stays in its cell."""
    parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [part.strip() for part in parts]


def table(text: str, first: str) -> list[dict[str, str]]:
    """The rows of the table in *text* whose first header cell is *first*,
    by header; a missing table fails, naming it."""
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if line.startswith("|") and cells(line)[0] == first:
            head = cells(line)
            rows = []
            for row in lines[number + 2 :]:
                if not row.startswith("|"):
                    break
                rows.append(dict(zip(head, cells(row))))
            return rows
    raise LookupError(f"no table with the first column {first!r}")


def unticked(cell: str) -> str:
    """A cell that is one code span, without its backticks."""
    found = re.fullmatch(r"`([^`]*)`", cell)
    return found.group(1) if found else cell


def slugs(path: Path) -> set[str]:
    """The anchors GitHub gives the headings of a page: lower case, marks
    but ``-`` and ``_`` dropped, spaces as ``-``, ``-1`` for a repeat."""
    out: set[str] = set()
    seen: dict[str, int] = {}
    for _, line in prose_lines(text_of(path)):
        found = _HEADING.match(line)
        if not found:
            continue
        slug = re.sub(r"[^\w\- ]", "", found.group(2).strip().lower())
        slug = slug.replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        out.add(slug if count == 0 else f"{slug}-{count}")
    return out


def links(path: Path) -> list[tuple[int, str]]:
    """``(line, target)`` of each inline or reference link outside code."""
    out: list[tuple[int, str]] = []
    for number, line in prose_lines(text_of(path)):
        bare = _SPAN.sub("", line)
        out.extend((number, a or b) for a, b in _LINK.findall(bare))
    return out


@dataclass(frozen=True)
class Block:
    """A fenced block of a page: its opening line (1-based), language, body
    and the marker before it, if any."""

    page: str
    line: int
    lang: str
    body: tuple[str, ...]
    marker: str | None

    @property
    def label(self) -> str:
        """A short test ID: ``output.md:29``."""
        return f"{Path(self.page).name}:{self.line}"


def marker_above(lines: list[str], start: int) -> str | None:
    """The ``docs-example`` marker of the fence at *start* (0-based): the
    first comment above it that is not a markdownlint one, blank lines
    between (a marker may run over several lines)."""
    end = start - 1
    while end >= 0 and (
        not lines[end].strip() or lines[end].lstrip().startswith("<!-- mark")
    ):
        end -= 1
    if end < 0 or not lines[end].endswith("-->"):
        return None
    top = end
    while top > max(0, end - 4) and not lines[top].lstrip().startswith("<!--"):
        top -= 1
    found = _MARKER.match(folded(" ".join(lines[top : end + 1])))
    return found.group(1) if found else None


def blocks(path: Path) -> list[Block]:
    """Every fenced block of a page, in order."""
    lines = text_of(path).splitlines()
    out = []
    number = 0
    while number < len(lines):
        found = _FENCE.match(lines[number])
        if not found:
            number += 1
            continue
        end = number + 1
        while end < len(lines) and not lines[end].strip().startswith(found.group(1)):
            end += 1
        out.append(
            Block(
                name_of(path),
                number + 1,
                found.group(2),
                tuple(lines[number + 1 : end]),
                marker_above(lines, number),
            )
        )
        number = end + 1
    return out


def directives(marker: str) -> dict[str, str]:
    """The parts of a marker: ``run: licenseid detect -v LICENSE; head`` is
    ``{"run": "licenseid detect -v LICENSE", "head": ""}``."""
    out = {}
    for part in marker.split(";"):
        key, _, value = part.strip().partition(":")
        out[key.strip()] = value.strip()
    return out


def commands(body: tuple[str, ...]) -> list[tuple[str, list[str]]]:
    """Each ``$ `` line of a console block, with the lines it prints."""
    out: list[tuple[str, list[str]]] = []
    for line in body:
        if line.startswith("$ "):
            out.append((line[2:], []))
        elif out:
            out[-1][1].append(line)
    return out


def json_like(want: object, got: object, where: str = "$") -> list[str]:
    """Where *got* differs from the shape *want* shows. In *want* a key
    ``"..."`` stands for keys not shown, a list whose one item is a string
    starting ``...`` (or ``...``, Python's Ellipsis) for any list, and
    Ellipsis for any value."""
    if want is Ellipsis or (
        isinstance(want, list)
        and len(want) == 1
        and (want[0] is Ellipsis or str(want[0]).startswith("..."))
    ):
        return []
    if isinstance(want, dict) and isinstance(got, dict):
        shown = {k: v for k, v in want.items() if k != "..."}
        keys = set(shown) <= set(got) if "..." in want else set(shown) == set(got)
        if not keys:
            return [f"{where}: keys {sorted(shown)}, got {sorted(got)}"]
        return [e for k in shown for e in json_like(shown[k], got[k], f"{where}.{k}")]
    if isinstance(want, list) and isinstance(got, list) and len(want) == len(got):
        return [
            e
            for n, (w, g) in enumerate(zip(want, got))
            for e in json_like(w, g, f"{where}[{n}]")
        ]
    return [] if want == got else [f"{where}: {want!r} shown, got {got!r}"]


@dataclass(frozen=True)
class PythonStep:
    """One top-level statement of a Python block: its source, and the value
    the page says it gives (``has_want``), from a ``# <literal>`` comment at
    its end or on the line after it."""

    line: int
    source: str
    is_expression: bool
    has_want: bool
    want: object = None


def _comments(source: str) -> dict[int, str]:
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return {
        t.start[0]: t.string[1:].strip() for t in tokens if t.type == tokenize.COMMENT
    }


def _literal(comment: str | None) -> tuple[bool, object]:
    if comment is None:
        return False, None
    try:
        return True, ast.literal_eval(comment)
    except (ValueError, SyntaxError):
        return False, None


def python_steps(source: str) -> list[PythonStep]:
    """The statements of a Python block, each with what the page says it
    gives. A comment that is no literal (``# who resolved it``) says nothing."""
    comments = _comments(source)
    lines = source.splitlines()
    out = []
    for node in ast.parse(source).body:
        end = node.end_lineno or node.lineno
        after = lines[end].strip() if end < len(lines) else ""
        comment = comments.get(end)
        if comment is None and after.startswith("#"):
            comment = comments.get(end + 1)
        has_want, want = _literal(comment)
        out.append(
            PythonStep(
                node.lineno,
                ast.get_source_segment(source, node) or "",
                isinstance(node, ast.Expr),
                has_want and isinstance(node, ast.Expr),
                want,
            )
        )
    return out
