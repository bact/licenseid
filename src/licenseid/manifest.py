# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Read the license field of a package manifest: package.json,
pyproject.toml, Cargo.toml, setup.cfg.

Each reader returns the raw values in file order; licenseid.markers resolves
them to licenses. A field is its author's declaration, so the caller treats a
value that resolves as certain.
"""

import configparser
import json
import os
import re

# PEP 621 table form, in any table: license = {text = "MIT"}
_RE_TOML_LICENSE_TABLE = re.compile(
    r'^license\s*=\s*\{[^}]*\btext\s*=\s*["\']([^"\']+)["\']',
    re.MULTILINE | re.IGNORECASE,
)
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
# The table and keys of each string that holds a license: PEP 639
# ([project]), Poetry and Cargo (an SPDX expression in each), and PEP 621's
# license table written as a table of its own or as a dotted key. A license
# key elsewhere means anything.
_TOML_LICENSE_KEYS = {
    "project": ("license", "license.text"),
    "tool.poetry": ("license",),
    "package": ("license",),
    "project.license": ("text",),
}


def json_license_values(stripped: str) -> list[str] | None:
    """The license field of a JSON object, or None if *stripped* is not
    JSON at all, so the caller can decide whether to read it as another
    format."""
    try:
        data = json.loads(stripped)
    except (ValueError, RecursionError):  # JSONDecodeError is a ValueError
        return None
    if not isinstance(data, dict):
        return []
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


def toml_license_values(text: str) -> list[str]:
    """The first inline-table value, then the first string value of each
    table in _TOML_LICENSE_KEYS: a manifest declares one license, and each
    value costs a database lookup, so a file of thousands of license lines
    yields at most five."""
    table_form = _RE_TOML_LICENSE_TABLE.search(text)
    values = [table_form.group(1)] if table_form else []
    by_table: dict[str, str] = {}
    table = ""
    for line in text.splitlines():
        header = _RE_TOML_HEADER.fullmatch(line)
        if header or _RE_TOML_ARRAY_HEADER.fullmatch(line):
            table = re.sub(r"\s", "", header.group(1)) if header else ""
            continue
        keys = _TOML_LICENSE_KEYS.get(table, ())
        if table in by_table:
            continue
        field = _RE_TOML_STRING.fullmatch(line)
        if field and field.group(1) in keys:
            value = field.group(2) or field.group(3) or ""
            if value.strip():
                by_table[table] = value
    if "package" in by_table and _RE_CARGO_SLASH_OR.fullmatch(by_table["package"]):
        by_table["package"] = " OR ".join(
            part.strip() for part in by_table["package"].split("/")
        )
    values.extend(by_table.values())
    return [value for value in values if value.strip()]


def ini_license_values(text: str) -> list[str]:
    """The license option of each INI section, in order. Malformed INI (no
    section header, a duplicate option, a stray %) has none."""
    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(_RE_INNER_SPACE_RUN.sub(" ", text))
    except configparser.Error:
        return []
    values = []
    for section in cfg.sections():
        try:
            values.append(cfg.get(section, "license", fallback="").strip())
        except configparser.Error:  # a stray % in this section only
            continue
    return [value for value in values if value]


def license_value_groups(text: str, ext: str) -> list[list[str]]:
    """The license values of each format *text* may be, chosen by its
    extension *ext* ("" for text with no file name, which is tried as each)."""
    stripped = text.strip()
    is_json_ext = ext == ".json"
    if is_json_ext or (not ext and stripped.startswith(("{", "["))):
        values = json_license_values(stripped)
        if values is not None:
            return [values]  # valid JSON: don't fall through to TOML/INI
        if is_json_ext:
            return []
        # Extensionless "[section]" text is INI/TOML, not JSON: fall through.
    groups: list[list[str]] = []
    # Text with no file name is TOML only if it starts like it: a README
    # showing a [project] example, or starting with a [![badge](...)], is not.
    if ext == ".toml" or (not ext and _starts_with_table(text)):
        groups.append(toml_license_values(text))
    if ext in (".cfg", ".ini", ""):
        groups.append(ini_license_values(text))
    return groups


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
