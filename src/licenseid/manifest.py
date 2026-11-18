# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Read the license field of a package manifest: package.json,
pyproject.toml, Cargo.toml, setup.cfg.

Each reader returns the raw values in file order, or None when the text is
not that format; licenseid.markers resolves them to licenses. A field is its
author's declaration, so the caller treats a value that resolves as certain.
"""

import configparser
import json
import os
import re
from collections.abc import Iterator

# PEP 621 table form, in any table: license = {text = "MIT"}, the text a basic
# string (group 1, escapes undone by _toml_unescape) or a literal one (group
# 2). The key ignores case in ASCII only: "lİcense" (U+0130) is no "license".
_RE_TOML_LICENSE_TABLE = re.compile(
    r"""(?a:license)\s*=\s*\{[^}]*\btext\s*=\s*(?:"((?:[^"\\]|\\.)*)"|'([^']*)')""",
    re.IGNORECASE,
)
# The line ends of a TOML file: CRLF and LF, and a lone CR as the command line
# reads it (not U+2028, U+0085, a form feed: ``str.splitlines()`` breaks there).
_RE_TOML_LINE_END = re.compile(r"\r\n|\r|\n")
# Any key, bare or quoted: a TOML file has at least one.
_RE_TOML_KEY = re.compile(r"""[ \t]*[\w."'-]+[ \t]*=""")
# The next string delimiter or comment on a line, a multi-line string's
# delimiter tried before a one-line string's.
_RE_TOML_QUOTE_OR_COMMENT = re.compile(r"\"\"\"|'''|[\"'#]")
# A table header, [project] or [tool.poetry], but not an array of tables
# ([[bin]]). No two neighbouring parts can match the same run of characters,
# so a long line cannot make either pattern backtrack.
_RE_TOML_HEADER = re.compile(r"[ \t]*\[([^\[\]]*)\][ \t]*(?:#.*)?")
_RE_TOML_ARRAY_HEADER = re.compile(r"[ \t]*\[\[[^\[\]]*\]\][ \t]*(?:#.*)?")
# A string value, as TOML writes it: a case-sensitive key and a basic string
# (group 2, with backslash escapes: a pair is one unit, so no two
# alternatives match the same run) or a literal one (group 3), with an
# optional trailing comment.
_RE_TOML_STRING = re.compile(
    r"""[ \t]*([\w.-]+)[ \t]*=[ \t]*"""
    r"""(?:"((?:[^"\\]|\\.)*)"|'([^']*)')[ \t]*(?:#.*)?"""
)
# One backslash escape of a TOML 1.0 basic string: \uXXXX, \UXXXXXXXX, or one
# character (the empty alternative is a backslash with nothing after it).
_RE_TOML_ESCAPE = re.compile(r"\\(u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}|.?)", re.DOTALL)
# The one-character escapes of TOML 1.0. TOML 1.1 adds \e and \xHH: a file
# that uses them is no TOML 1.0, and is read as no value (fail closed).
_TOML_SIMPLE_ESCAPES = {
    "b": "\b",
    "t": "\t",
    "n": "\n",
    "f": "\f",
    "r": "\r",
    '"': '"',
    "\\": "\\",
}
# A run of white space inside or at the end of a line. Older configparser
# (Python 3.10) scans it once per character of the key before it, so 50,000
# spaces after "license" took 9 s. Leading white space marks a continuation
# line, so it stays.
_RE_INNER_SPACE_RUN = re.compile(r"(?<=\S)[^\S\n]{2,}")
# configparser's own patterns for a section header and an option line.
_INI_SECTION = configparser.ConfigParser.SECTCRE
_INI_OPTION = configparser.ConfigParser.OPTCRE
# Cargo's tables: a crate's, and a workspace's, which its members inherit.
# Their "MIT/Apache-2.0" is read as OR by licenseid.resolveslash.
_CARGO_TABLES = ("package", "workspace.package")
# The table and keys of each string that holds a license: PEP 639
# ([project]), Poetry and Cargo (an SPDX expression in each), and PEP 621's
# license table written as a table of its own or as a dotted key. A license
# key elsewhere means anything.
_TOML_LICENSE_KEYS = {
    "project": ("license", "license.text"),
    "tool.poetry": ("license",),
    "project.license": ("text",),
    **{table: ("license",) for table in _CARGO_TABLES},
}
_NOT_JSON = object()


def _parse_json(stripped: str) -> object:
    """The JSON value of *stripped*, or _NOT_JSON."""
    try:
        return json.loads(stripped)
    except (ValueError, RecursionError):  # JSONDecodeError is a ValueError
        return _NOT_JSON


def json_license_values(data: dict[str, object]) -> list[str]:
    """The license field of a JSON object."""
    val = data.get("license") or data.get("License") or data.get("LICENSE")
    if isinstance(val, dict):  # npm's old object form: {"type": T, "url": U}
        # The type first; the URL only if the type is absent or names nothing.
        named = [val.get("type"), val.get("url")]
        values = [v for v in named if isinstance(v, str) and v]
        if values:
            return values
        val = None
    if isinstance(val, str) and val:
        return [val]
    # npm's old array form, one entry per license the user may choose. Each
    # entry is one operand without brackets: every operator binds at least
    # as tightly as OR.
    types = [_license_type(entry) for entry in _as_list(data.get("licenses"))]
    return [" OR ".join(types)] if types and all(types) else []


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _license_type(entry: object) -> str:
    """The license of one entry of npm's "licenses" array, "" if none."""
    if isinstance(entry, dict):
        entry = entry.get("type")
    return entry.strip() if isinstance(entry, str) else ""


def toml_license_values(text: str) -> list[str] | None:
    """The first inline-table value, then the first string value of each
    table in _TOML_LICENSE_KEYS: a manifest declares one license, and each
    value costs a database lookup, so a file of thousands of license lines
    yields at most six. None if no line outside a string holds a key."""
    table_form = ""
    by_table: dict[str, str] = {}
    table = ""
    has_key = False
    for line in _toml_lines(text):
        header = _RE_TOML_HEADER.fullmatch(line)
        if header or _RE_TOML_ARRAY_HEADER.fullmatch(line):
            table = re.sub(r"\s", "", header.group(1)) if header else ""
            continue
        has_key = has_key or bool(_RE_TOML_KEY.match(line))
        inline = None if table_form else _RE_TOML_LICENSE_TABLE.match(line)
        table_form = _decoded(inline) if inline else table_form
        value = "" if table in by_table else _license_string(line, table)
        if value:
            by_table[table] = value
    values = [table_form, *by_table.values()]
    return [value for value in values if value.strip()] if has_key else None


def _toml_text_lines(text: str) -> Iterator[str]:
    """The lines of TOML *text*. TOML ends a line at LF or CRLF (TOML 1.0,
    "Spec"); a lone CR ends one too, as the command line reads it
    (``textinput.normalize_newlines``), so the API and the command line agree.
    str.splitlines() also breaks at U+2028, U+0085, a form feed and more,
    which would cut a comment or a string in two."""
    yield from _RE_TOML_LINE_END.split(text)


def _toml_lines(text: str) -> Iterator[str]:
    """The lines of *text* outside multi-line strings, whose lines are
    text, not TOML: a header or a field there is none."""
    open_quote = ""
    for line in _toml_text_lines(text):
        if not open_quote:
            yield line
        open_quote = _open_string(line, open_quote)


def _open_string(line: str, quote: str) -> str:
    """The multi-line string delimiter still open at the end of *line*,
    given *quote*, the one open at its start ("" for none). A delimiter in a
    comment or a one-line string opens nothing."""
    pos = 0
    while True:
        if not quote:
            token = _RE_TOML_QUOTE_OR_COMMENT.search(line, pos)
            if not token or token.group() == "#":
                return ""
            quote, pos = token.group(), token.end()
        end = _string_end(line, pos, quote)
        if end < 0:
            # A one-line string cannot stay open: that is no TOML.
            return quote if len(quote) == 3 else ""
        quote, pos = "", end


def _string_end(line: str, pos: int, quote: str) -> int:
    """The index just past the delimiter at or after *pos* that closes a
    *quote* string, or -1. A basic string ('"') has backslash escapes; a
    literal one has none."""
    end = line.find(quote, pos)
    while end >= 0 and quote[0] == '"' and _escaped(line, end):
        end = line.find(quote, end + 1)
    if end < 0:
        return -1
    end += len(quote)
    # A multi-line string may end in one or two quotes of its own, just
    # before its delimiter: """say "hi"""" holds 'say "hi"'.
    for _ in range(2 if len(quote) == 3 else 0):
        end += line.startswith(quote[0], end)
    return end


def _escaped(line: str, index: int) -> bool:
    """Whether an odd run of backslashes comes just before *index*."""
    start = index
    while start and line[start - 1] == "\\":
        start -= 1
    return (index - start) % 2 == 1


def _license_string(line: str, table: str) -> str:
    """The value of *line* if it is a license string of *table*, else ""."""
    field = _RE_TOML_STRING.fullmatch(line)
    if field and field.group(1) in _TOML_LICENSE_KEYS.get(table, ()):
        return _decoded(field, 2)
    return ""


def _decoded(match: re.Match[str], first: int = 1) -> str:
    """The string a match of :data:`_RE_TOML_STRING` or
    :data:`_RE_TOML_LICENSE_TABLE` read: its basic string (group *first*)
    with the escapes undone, or its literal string (the group after) as
    written; "" for none or for an escape TOML 1.0 does not have."""
    basic, literal = match.group(first), match.group(first + 1)
    if basic is None:
        return literal or ""
    return _toml_unescape(basic) or ""


def _toml_unescape(raw: str) -> str | None:
    """*raw*, the inside of a TOML basic string, with its escapes undone:
    ``\\b \\t \\n \\f \\r \\" \\\\ \\uXXXX \\UXXXXXXXX``. None for any
    other escape (``\\x41``, ``\\e``, a short ``\\u12``) and for a code point
    that is no Unicode scalar value (a surrogate, past U+10FFFF), as a TOML
    parser refuses the file. A literal string is never passed here."""
    if "\\" not in raw:
        return raw

    def one(escape: re.Match[str]) -> str:
        code = escape.group(1)
        if code[:1] in ("u", "U"):
            point = int(code[1:], 16)
            if 0xD800 <= point <= 0xDFFF or point > 0x10FFFF:
                raise ValueError(code)
            return chr(point)
        if code not in _TOML_SIMPLE_ESCAPES:
            raise ValueError(code)
        return _TOML_SIMPLE_ESCAPES[code]

    try:
        return _RE_TOML_ESCAPE.sub(one, raw)
    except ValueError:
        return None


def _has_bad_ini_line(text: str) -> bool:
    """Whether a line of *text* is one configparser surely refuses: a line
    that is no header, no option and no continuation. configparser collects
    every such line into one error message by appending to a string, which is
    quadratic on Python 3.10 to 3.14.3 at least (100,000 bad lines took 2.8 s
    on 3.10 and 3.3 s on 3.13; 3.14.10 joins the parts and takes 0.35 s), so
    ini_license_values stops at the first. It follows the parser's default
    rules (``_read``) and judges one way only: a line it calls bad raises in
    configparser; a bad line it misses costs time, never an answer
    (tests/test_ini_bad_lines.py checks it against configparser)."""
    in_section = in_option = False
    indent_level = 0
    for line in text.split("\n"):  # as io.StringIO splits, not splitlines()
        value = line.strip()
        if not value or value[0] in "#;":
            continue
        indent = len(line) - len(line.lstrip())
        if in_option and indent > indent_level:
            continue  # a continuation line
        indent_level = indent
        if _INI_SECTION.match(value):
            in_section, in_option = True, False
            continue
        option = _INI_OPTION.match(value)
        if not in_section or not option or not option.group("option").strip():
            return True
        in_option = True
    return False


def ini_license_values(text: str) -> list[str] | None:
    """The license option of each INI section, in order. None for malformed
    INI (no section header, a duplicate option, a stray %) or INI with no
    option at all ("[MIT]" is no manifest)."""
    text = _RE_INNER_SPACE_RUN.sub(" ", text)
    if _has_bad_ini_line(text):
        return None
    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(text)
    except configparser.Error:
        return None
    if not any(cfg.options(section) for section in cfg.sections()):
        return None
    values = []
    for section in cfg.sections():
        try:
            values.append(cfg.get(section, "license", fallback="").strip())
        except configparser.Error:  # a stray % in this section only
            continue
    return [value for value in values if value]


def license_value_groups(text: str, ext: str) -> list[list[str]]:
    """The license values of each manifest format *text* is, chosen by its
    extension *ext* ("" for text with no file name, which is tried as each).
    No group at all means *text* is no manifest; an empty one, a manifest
    with no license value."""
    stripped = text.strip()
    is_json_ext = ext == ".json"
    if is_json_ext or (not ext and stripped.startswith(("{", "["))):
        data = _parse_json(stripped)
        if data is not _NOT_JSON:
            # Valid JSON: don't fall through to TOML/INI.
            return [json_license_values(data)] if isinstance(data, dict) else []
        if is_json_ext:
            return []
        # Extensionless "[section]" text is INI/TOML, not JSON: fall through.
    groups: list[list[str] | None] = []
    # Text with no file name is TOML only if it starts like it: a README
    # showing a [project] example, or starting with a [![badge](...)], is not.
    if ext == ".toml" or (not ext and _starts_with_table(text)):
        groups.append(toml_license_values(text))
    if ext in (".cfg", ".ini", ""):
        groups.append(ini_license_values(text))
    return [group for group in groups if group is not None]


def extension(file_path: str | None) -> str:
    """The lowercase extension of *file_path*, "" for text or none."""
    return os.path.splitext(file_path)[1].lower() if file_path else ""


def _starts_with_table(text: str) -> bool:
    """Whether the first line that is not blank or a # comment is a whole
    TOML table header."""
    for line in _toml_text_lines(text):
        if line.strip() and not line.lstrip().startswith("#"):
            return bool(
                _RE_TOML_HEADER.fullmatch(line) or _RE_TOML_ARRAY_HEADER.fullmatch(line)
            )
    return False
