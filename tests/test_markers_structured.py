# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Direct unit tests for MarkerDetector._detect_structured_format().

Characterization tests written before the complexity refactor (see
working-docs/design/complexity-and-file-size-roadmap.md) to pin down JSON,
TOML, and INI license-field detection, which had no direct tests: the
extension gating, the JSON early return, per-format scores, and how
malformed input degrades.
"""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring
# pylint: disable=protected-access

import sqlite3
import sys
from collections.abc import Generator

import pytest
from conftest import make_memory_db_path

from licenseid.database import LicenseDatabase
from licenseid.markers import MarkerDetector
from licenseid.types import CandidateMatch


@pytest.fixture
def detector() -> Generator[MarkerDetector, None, None]:
    db_path, keep_alive = make_memory_db_path("test_markers_structured")
    insert = (
        "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
        "is_fsf_libre) VALUES (?, ?, ?, ?, ?)"
    )
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(insert, ("MIT", "MIT License", True, True, True))
        conn.execute(insert, ("Apache-2.0", "Apache License 2.0", True, True, True))
        conn.commit()
    yield MarkerDetector(LicenseDatabase(db_path))
    keep_alive.close()


def _summary(candidates: list[CandidateMatch]) -> list[tuple[str, float]]:
    return [(c["license_id"], c.get("score", 0.0)) for c in candidates]


# --- JSON ---


@pytest.mark.parametrize(
    "text",
    [
        '{"license": "MIT"}',
        '{"License": "MIT"}',
        '{"LICENSE": "MIT"}',
        '  \n{"name": "x", "license": "MIT"}\n',
    ],
)
def test_json_ext_resolves_license_key(detector: MarkerDetector, text: str) -> None:
    result = detector._detect_structured_format(text, ".json")
    assert _summary(result) == [("MIT", 1.0)]


def test_json_license_resolved_by_name(detector: MarkerDetector) -> None:
    result = detector._detect_structured_format(
        '{"license": "Apache License 2.0"}', ".json"
    )
    assert _summary(result) == [("Apache-2.0", 1.0)]


def test_json_without_ext_routes_object_to_json(detector: MarkerDetector) -> None:
    result = detector._detect_structured_format('{"license": "MIT"}')
    assert _summary(result) == [("MIT", 1.0)]


@pytest.mark.parametrize(
    "text",
    [
        '["MIT"]',
        '[{"license": "MIT"}]',
        "not json at all",
        '{"license": "MIT"',
        "",
    ],
)
def test_json_non_object_or_invalid_returns_nothing(
    detector: MarkerDetector, text: str
) -> None:
    assert not detector._detect_structured_format(text, ".json")


def test_json_parse_failure_does_not_fall_through(detector: MarkerDetector) -> None:
    """The JSON branch always returns, so INI/TOML-looking text under a
    .json extension is never re-parsed by the other branches."""
    ini_like = "[metadata]\nlicense = MIT\n"
    toml_like = 'license = {text = "MIT"}'
    assert not detector._detect_structured_format(ini_like, ".json")
    assert not detector._detect_structured_format(toml_like, ".json")


@pytest.mark.parametrize(
    "value",
    ['{"name": "MIT"}', '["MIT"]', "42", "true", "null", '""', '{"type": 42}'],
)
def test_json_non_string_or_empty_value_returns_nothing(
    detector: MarkerDetector, value: str
) -> None:
    """An object without a string "type", lists, numbers, booleans, null,
    and the empty string are not resolved."""
    assert not detector._detect_structured_format('{"license": ' + value + "}", ".json")


def test_json_truthy_non_string_license_shadows_valid_key(
    detector: MarkerDetector,
) -> None:
    """Quirk: the key fallback is `license or License or LICENSE`, so a
    truthy non-string "license" hides a valid "License"."""
    text = '{"license": ["MIT"], "License": "MIT"}'
    assert not detector._detect_structured_format(text, ".json")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # npm's old object form.
        ('{"license": {"type": "MIT", "url": "https://x"}}', "MIT"),
        # npm's old array form: the user may choose any one.
        (
            '{"licenses": [{"type": "MIT"}, {"type": "Apache-2.0"}]}',
            "Apache-2.0 OR MIT",
        ),
        ('{"licenses": ["MIT", "Apache-2.0"]}', "Apache-2.0 OR MIT"),
        ('{"licenses": [{"type": "MIT"}]}', "MIT"),
        # An entry that is itself an expression stays one operand: AND binds
        # tighter than OR.
        (
            '{"licenses": [{"type": "MIT AND Apache-2.0"}, {"type": "MIT"}]}',
            "Apache-2.0 AND MIT OR MIT",
        ),
        # The "license" key comes first.
        ('{"license": "MIT", "licenses": [{"type": "Apache-2.0"}]}', "MIT"),
    ],
    ids=["object", "array", "array-of-strings", "array-of-one", "nested", "both"],
)
def test_json_npm_legacy_forms_resolve(
    detector: MarkerDetector, text: str, expected: str
) -> None:
    assert _summary(detector._detect_structured_format(text, ".json")) == [
        (expected, 1.0)
    ]


@pytest.mark.parametrize(
    "text",
    [
        '{"licenses": [{"type": "MIT"}, {"url": "https://x"}]}',  # one unnamed
        '{"licenses": []}',
        '{"licenses": "MIT"}',
    ],
    ids=["unnamed-entry", "empty", "not-a-list"],
)
def test_json_npm_array_with_a_gap_is_not_read(
    detector: MarkerDetector, text: str
) -> None:
    """Every entry must name its license: an OR that leaves one out would
    answer for fewer licenses than the file offers."""
    assert not detector._detect_structured_format(text, ".json")


# --- TOML ---


@pytest.mark.parametrize(
    "text",
    [
        'license = {text = "MIT"}',
        "license = {text = 'MIT'}",
        'License = {text = "MIT"}',
        'license = { file = "LICENSE", text = "MIT" }',
        '[project]\nname = "x"\nlicense = {text = "MIT"}\n',
    ],
)
def test_toml_table_form_resolves(detector: MarkerDetector, text: str) -> None:
    result = detector._detect_structured_format(text, ".toml")
    assert _summary(result) == [("MIT", 1.0)]


def test_toml_commented_out_line_not_matched(detector: MarkerDetector) -> None:
    text = '# license = {text = "MIT"}\n'
    assert not detector._detect_structured_format(text, ".toml")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('[project]\nlicense = "MIT"\n', "MIT"),  # PEP 639
        ("[project]\nlicense = 'MIT'\n", "MIT"),  # a literal string
        ('[project]\nlicense = "MIT"  # SPDX\n', "MIT"),
        ('[ project ]\n  license="MIT"\n', "MIT"),
        ('[tool.poetry]\nname = "x"\nlicense = "MIT"\n', "MIT"),
        ('[package]\nname = "x"\nlicense = "MIT OR Apache-2.0"\n', "Apache-2.0 OR MIT"),
        ('[tool.x]\nlicense = "GPL"\n[project]\nlicense = "MIT"\n', "MIT"),
    ],
    ids=["pep639", "literal", "comment", "spacing", "poetry", "cargo", "later-table"],
)
def test_toml_string_form_resolves(
    detector: MarkerDetector, text: str, expected: str
) -> None:
    result = detector._detect_structured_format(text, ".toml")
    assert _summary(result) == [(expected, 1.0)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('[project]\nname = "x"\n[project.license]\ntext = "MIT"\n', "MIT"),
        ('[project]\nlicense.text = "MIT"\n', "MIT"),
        ('[project.license]\nfile = "LICENSE"\n', None),
        ('[tool.x.license]\ntext = "MIT"\n', None),
        ('[package]\nname = "x"\n[[bin]]\nlicense = "MIT"\n', None),
    ],
    ids=["sub-table", "dotted-key", "sub-table-file", "other-sub-table", "array"],
)
def test_toml_pep621_table_written_out(
    detector: MarkerDetector, text: str, expected: str | None
) -> None:
    """PEP 621's license table as a table of its own or a dotted key; an
    array of tables ([[bin]]) is not the table above it."""
    result = _summary(detector._detect_structured_format(text, ".toml"))
    assert result == ([(expected, 1.0)] if expected else [])


@pytest.mark.parametrize(
    "text",
    [
        'license = "MIT"\n',  # no table: a Python assignment, say
        '[tool.other]\nlicense = "MIT"\n',
        '[[package]]\nlicense = "MIT"\n',  # an array of tables
        '[project]\n# license = "MIT"\n',
        '[project]\nLicense = "MIT"\n',  # TOML keys are case-sensitive
        '[project]\nlicense = {file = "LICENSE"}\n',
        '[project]\nlicense = ""\n',
        '[project]\nlicense = "see LICENSE file"\n',
        # Starts like a header but is not one: the table stays tool.other.
        '[tool.other]\nrows = [\n[package], 1\n]\nlicense = "MIT"\n',
    ],
    ids=[
        "no-table",
        "other-table",
        "array-of-tables",
        "commented",
        "capitalised-key",
        "file-only",
        "empty",
        "free-text",
        "not-a-header",
    ],
)
def test_toml_string_form_elsewhere_is_not_read(
    detector: MarkerDetector, text: str
) -> None:
    assert not detector._detect_structured_format(text, ".toml")


@pytest.mark.parametrize(
    "text",
    [
        '[project]\nlicense = "MIT"\n',
        '# pyproject\n\n[project]\nlicense = "MIT"\n',
        '[build-system]\nrequires = []\n[project]\nlicense = "MIT"\n',
        '[project] # metadata\r\nlicense = "MIT"\r\n',
        '[project]\nlicense = {text = "MIT"}',
        # A Cargo.toml may open with an array of tables.
        '[[bin]]\nname = "x"\n\n[package]\nlicense = "MIT"\n',
        "# setup\n[metadata]\nlicense = MIT\n",  # INI
    ],
    ids=[
        "header-first",
        "after-comments",
        "after-another-table",
        "comment-and-crlf",
        "table-form",
        "array-of-tables-first",
        "ini",
    ],
)
def test_no_ext_manifest_resolves(detector: MarkerDetector, text: str) -> None:
    assert _summary(detector._detect_structured_format(text)) == [("MIT", 1.0)]


# --- INI ---


@pytest.mark.parametrize(
    ("text", "ext", "expected"),
    [
        ("[metadata]\nlicense = MIT\n", ".cfg", "MIT"),
        ("[metadata]\nlicense = MIT\n", ".ini", "MIT"),
        ("[metadata]\nlicense =   Apache License 2.0   \n", ".cfg", "Apache-2.0"),
        (
            "[a]\nname = x\n[b]\nlicense = MIT\n[c]\nlicense = Apache-2.0\n",
            ".ini",
            "MIT",
        ),
        ("[a]\nlicense =\n[b]\nlicense = Apache-2.0\n", ".ini", "Apache-2.0"),
        # Quirk: [DEFAULT] is no section, but every section inherits it.
        ("[DEFAULT]\nlicense = MIT\n[a]\nname = x\n", ".ini", "MIT"),
        ("[a]\nlicense = see LICENSE file\n[b]\nlicense = MIT\n", ".ini", "MIT"),
        ("[a]\nlicense = 100% free\n[b]\nlicense = MIT\n", ".ini", "MIT"),
        ("[a]\nlicense  =  MIT  OR\tApache-2.0  \n", ".cfg", "Apache-2.0 OR MIT"),
        # A deeper indent continues the value; collapsing it would not.
        ("[a]\n  license = MIT\n    OR Apache-2.0\n", ".cfg", "Apache-2.0 OR MIT"),
    ],
    ids=[
        "cfg",
        "ini",
        "name-and-spaces",
        "first-section-wins",
        "empty-skipped",
        "default-inherited",
        "unresolved-then-next",
        "bad-interpolation-then-next",
        "space-runs",
        "indented-continuation",
    ],
)
def test_ini_license_resolves(
    detector: MarkerDetector, text: str, ext: str, expected: str
) -> None:
    result = detector._detect_structured_format(text, ext)
    assert _summary(result) == [(expected, 1.0)]


@pytest.mark.parametrize(
    ("text", "ext"),
    [
        ("[a]\nname = x\n[b]\nk = v\n", ".ini"),
        # Free text is no phantom is_spdx candidate, with or without a name.
        ("[docs]\nlicense: see LICENSE file\n", ".ini"),
        ("[docs]\nlicense: see LICENSE file\n", ""),
        ("license = MIT\n", ".ini"),  # no section header
        ("[a]\nlicense = MIT\nlicense = Apache-2.0\n", ".ini"),  # duplicate
        ("[a]\nlicense = 100% free\n", ".ini"),  # bad interpolation
        ('license = {text = "MIT"}', ".cfg"),  # TOML is not read from .cfg
    ],
    ids=[
        "no-license",
        "free-text",
        "free-text-no-ext",
        "no-section",
        "duplicate-option",
        "bad-interpolation",
        "toml-under-cfg",
    ],
)
def test_ini_without_a_license_returns_nothing(
    detector: MarkerDetector, text: str, ext: str
) -> None:
    assert not detector._detect_structured_format(text, ext)


# --- extension gating ---


@pytest.mark.parametrize("ext", [".yaml", ".txt", ".md"])
def test_unknown_extension_returns_nothing(detector: MarkerDetector, ext: str) -> None:
    for text in ('license = {text = "MIT"}', "[a]\nlicense = MIT\n"):
        assert not detector._detect_structured_format(text, ext)


# --- no extension: TOML then INI both run ---


@pytest.mark.parametrize(
    "text",
    [
        'license = {text = "MIT"}',  # no table: not TOML that starts like it
        '# Usage\n```toml\n[project]\nlicense = "MIT"\n```\n',
        '# Usage\n```toml\n[project]\nlicense = {text = "MIT"}\n```\n',
        '[![PyPI](https://x)](https://y)\n[project]\nlicense = "MIT"\n',
        '[![PyPI](https://x)](https://y)\n[project]\nlicense = {text = "MIT"}\n',
    ],
    ids=[
        "bare-line",
        "readme-string-form",
        "readme-table-form",
        "badge-string-form",
        "badge-table-form",
    ],
)
def test_no_ext_text_not_starting_as_toml_is_not_read_as_toml(
    detector: MarkerDetector, text: str
) -> None:
    """A README piped in (a badge first, a [project] example inside) is not
    a manifest, in either form; since the field scores 1.0, the example
    would be a certain answer."""
    assert not detector._detect_structured_format(text)


def test_no_ext_toml_and_ini_both_run_toml_first(detector: MarkerDetector) -> None:
    text = (
        '# metadata\n[a]\nlicense = Apache-2.0\n[project]\nlicense = {text = "MIT"}\n'
    )
    result = detector._detect_structured_format(text)
    assert _summary(result) == [("MIT", 1.0), ("Apache-2.0", 1.0)]


def test_no_ext_toml_table_not_reparsed_as_ini_phantom_candidate(
    detector: MarkerDetector,
) -> None:
    """Regression: with no extension the INI branch also reads the PEP 621
    table's raw value '{text = "MIT"}' under [project]; it must not become a
    phantom candidate alongside the real MIT one."""
    text = '# pyproject\n[project]\nlicense = {text = "MIT"}\n'
    result = detector._detect_structured_format(text)
    assert _summary(result) == [("MIT", 1.0)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[metadata]\nlicense = MIT\n", [("MIT", 1.0)]),
        (
            '[project]\nlicense = {text = "MIT"}\n',
            [("MIT", 1.0)],
        ),
    ],
    ids=["ini", "toml_table"],
)
def test_no_ext_section_header_first_falls_through_from_json(
    detector: MarkerDetector, text: str, expected: list[tuple[str, float]]
) -> None:
    """Regression: extensionless text starting with '[' is tried as JSON
    first; when that fails it must fall through to TOML/INI (as .cfg/.toml
    files already do) instead of being swallowed by the JSON branch."""
    assert _summary(detector._detect_structured_format(text)) == expected


def test_no_ext_valid_json_still_does_not_fall_through(
    detector: MarkerDetector,
) -> None:
    assert not detector._detect_structured_format('{"name": "x"}')
    assert not detector._detect_structured_format('["MIT"]')


_NESTING_DEPTH = sys.getrecursionlimit() + 1000


@pytest.mark.parametrize("text", ["[" * _NESTING_DEPTH, '{"a":' * _NESTING_DEPTH])
@pytest.mark.parametrize("ext", ["", ".json"])
def test_json_deep_nesting_does_not_crash(
    detector: MarkerDetector, text: str, ext: str
) -> None:
    """Regression: json.loads raises RecursionError (not a ValueError) on
    nesting deeper than the recursion limit; it must degrade to "no match",
    not crash detect()/match()."""
    assert not detector._detect_structured_format(text, ext)


# --- resolve_license_value (callee) ---


def test_resolve_spdx_url(detector: MarkerDetector) -> None:
    result = detector.resolve_license_value("https://spdx.org/licenses/MIT/", 0.9)
    assert _summary(result) == [("MIT", 0.9)]


@pytest.mark.parametrize(
    "value",
    [
        "Totally-Unknown-License",
        "see LICENSE file",
        '{text = "MIT"}',
        "(MIT",
        "Dual OR Commercial",
        "NOASSERTION",
        "NONE",
        "UNLICENSED",
    ],
)
def test_resolve_unrecognised_value_returns_nothing(
    detector: MarkerDetector, value: str
) -> None:
    """Regression: arbitrary text used to become a phantom candidate with
    is_spdx=True at a fixed high score."""
    assert not detector.resolve_license_value(value, 0.95)


@pytest.mark.parametrize(
    ("value", "expected_id", "is_spdx"),
    [
        ("MIT OR Apache-2.0", "Apache-2.0 OR MIT", True),
        ("MIT WITH Font-exception-2.0", "MIT WITH Font-exception-2.0", True),
        ("LicenseRef-foo", "LicenseRef-foo", True),
        ("GPL-3.0 or Commercial", "GPL-3.0-only OR Commercial", False),
        ("LicenseRef-foo AND Commercial", "LicenseRef-foo AND Commercial", False),
    ],
)
def test_resolve_valid_expression_or_licenseref_yields_synthetic_candidate(
    detector: MarkerDetector, value: str, expected_id: str, is_spdx: bool
) -> None:
    """Well-formed values with no DB row are kept as synthetic candidates;
    is_spdx is False if any part of the expression is unknown."""
    result = detector.resolve_license_value(value, 0.95)
    assert len(result) == 1
    assert result[0]["license_id"] == expected_id
    assert result[0]["is_spdx"] is is_spdx
    assert result[0]["search_text"] == ""
    assert result[0]["score"] == 0.95


@pytest.mark.parametrize("value", ["", "   "])
def test_resolve_blank_value_returns_nothing(
    detector: MarkerDetector, value: str
) -> None:
    assert not detector.resolve_license_value(value, 0.95)
