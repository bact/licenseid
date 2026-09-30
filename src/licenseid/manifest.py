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
# The string form, as TOML writes it: a case-sensitive key and a basic or a
# literal string, with an optional trailing comment.
_RE_TOML_LICENSE_STRING = re.compile(
    r"""[ \t]*license[ \t]*=[ \t]*(?:"([^"\\]*)"|'([^']*)')[ \t]*(?:#.*)?"""
)
# Cargo's old spelling of OR, "MIT/Apache-2.0", still common in crates.
_RE_CARGO_SLASH_OR = re.compile(r"[\w.+-]+(?:[ \t]*/[ \t]*[\w.+-]+)+")
# Tables whose license key is a string: PEP 639 ([project]), Poetry and Cargo
# (an SPDX expression in each). A license key elsewhere means anything.
_TOML_LICENSE_TABLES = frozenset({"project", "tool.poetry", "package"})


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
    return [val] if isinstance(val, str) and val else []


def toml_license_values(text: str) -> list[str]:
    """The first table-form value, then the first string-form value of each
    table in _TOML_LICENSE_TABLES: a manifest declares one license, and each
    value costs a database lookup, so a file of thousands of license lines
    yields at most four."""
    table_form = _RE_TOML_LICENSE_TABLE.search(text)
    values = [table_form.group(1)] if table_form else []
    by_table: dict[str, str] = {}
    table = ""
    for line in text.splitlines():
        header = _RE_TOML_HEADER.fullmatch(line)
        if header:
            table = re.sub(r"\s", "", header.group(1))
            continue
        if table in _TOML_LICENSE_TABLES and table not in by_table:
            field = _RE_TOML_LICENSE_STRING.fullmatch(line)
            value = (field.group(1) or field.group(2) or "") if field else ""
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
        cfg.read_string(text)
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
    if ext in (".toml", ""):
        groups.append(toml_license_values(text))
    if ext in (".cfg", ".ini", ""):
        groups.append(ini_license_values(text))
    return groups
