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

# PEP 621 table form, in any table: license = {text = "MIT"}
_RE_TOML_LICENSE_TABLE = re.compile(
    r'license\s*=\s*\{[^}]*\btext\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE
)
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
# A string value, as TOML writes it: a case-sensitive key and a basic or a
# literal string, with an optional trailing comment.
_RE_TOML_STRING = re.compile(
    r"""[ \t]*([\w.-]+)[ \t]*=[ \t]*(?:"([^"\\]*)"|'([^']*)')[ \t]*(?:#.*)?"""
)
# A run of white space inside or at the end of a line. Older configparser
# (Python 3.10) scans it once per character of the key before it, so 50,000
# spaces after "license" took 9 s. Leading white space marks a continuation
# line, so it stays.
_RE_INNER_SPACE_RUN = re.compile(r"(?<=\S)[^\S\n]{2,}")
# Cargo's old spelling of OR, "MIT/Apache-2.0", still common in crates.
_RE_CARGO_SLASH_OR = re.compile(r"[\w.+-]+(?:[ \t]*/[ \t]*[\w.+-]+)+")
# Cargo's tables: a crate's, and a workspace's, which its members inherit.
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
    if isinstance(val, dict):  # npm's old object form: {"type": "MIT", ...}
        val = val.get("type")
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
        table_form = inline.group(1) if inline else table_form
        value = "" if table in by_table else _license_string(line, table)
        if value:
            by_table[table] = _cargo_or(value) if table in _CARGO_TABLES else value
    values = [table_form, *by_table.values()]
    return [value for value in values if value.strip()] if has_key else None


def _toml_lines(text: str) -> Iterator[str]:
    """The lines of *text* outside multi-line strings, whose lines are
    text, not TOML: a header or a field there is none."""
    open_quote = ""
    for line in text.splitlines():
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
    return end + len(quote) if end >= 0 else -1


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
        return field.group(2) or field.group(3) or ""
    return ""


def _cargo_or(value: str) -> str:
    """Cargo's "MIT/Apache-2.0" as "MIT OR Apache-2.0"."""
    if _RE_CARGO_SLASH_OR.fullmatch(value):
        return " OR ".join(part.strip() for part in value.split("/"))
    return value


def ini_license_values(text: str) -> list[str] | None:
    """The license option of each INI section, in order. None for malformed
    INI (no section header, a duplicate option, a stray %) or INI with no
    option at all ("[MIT]" is no manifest)."""
    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(_RE_INNER_SPACE_RUN.sub(" ", text))
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
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            return bool(
                _RE_TOML_HEADER.fullmatch(line) or _RE_TOML_ARRAY_HEADER.fullmatch(line)
            )
    return False
