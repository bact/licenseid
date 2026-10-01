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
    ],
    ids=["header-first", "after-comments", "after-another-table"],
)
def test_no_ext_text_that_starts_as_toml_reads_the_string_form(
    detector: MarkerDetector, text: str
) -> None:
    assert _summary(detector._detect_structured_format(text)) == [("MIT", 1.0)]


def test_no_ext_prose_with_a_toml_example_is_not_a_manifest(
    detector: MarkerDetector,
) -> None:
    """A README piped in shows a [project] example; the license in it is the
    reader's, not this project's."""
    text = (
        "# Usage\nSet the license in your pyproject.toml:\n\n```toml\n"
        '[project]\nlicense = "MIT"\n```\n'
    )
    assert not detector._detect_structured_format(text)
    # A .toml file is a manifest wherever its tables start.
    toml = 'name = "x"\n[project]\nlicense = "MIT"\n'
    assert _summary(detector._detect_structured_format(toml, ".toml")) == [("MIT", 1.0)]


def test_no_ext_python_assignment_is_not_a_license_field(
    detector: MarkerDetector,
) -> None:
    """Extensionless text (--text input) runs the TOML reader too, so the
    string form is read only inside a manifest table."""
    text = 'import os\nlicense = "MIT"\nprint(license)\n'
    assert not detector._detect_structured_format(text)


# --- INI ---


@pytest.mark.parametrize("ext", [".cfg", ".ini"])
def test_ini_section_license_resolves(detector: MarkerDetector, ext: str) -> None:
    result = detector._detect_structured_format("[metadata]\nlicense = MIT\n", ext)
    assert _summary(result) == [("MIT", 1.0)]


def test_ini_license_name_and_whitespace(detector: MarkerDetector) -> None:
    text = "[metadata]\nlicense =   Apache License 2.0   \n"
    result = detector._detect_structured_format(text, ".cfg")
    assert _summary(result) == [("Apache-2.0", 1.0)]


def test_ini_first_section_with_license_wins(detector: MarkerDetector) -> None:
    text = "[a]\nname = x\n[b]\nlicense = MIT\n[c]\nlicense = Apache-2.0\n"
    result = detector._detect_structured_format(text, ".ini")
    assert _summary(result) == [("MIT", 1.0)]


def test_ini_empty_license_skipped_to_next_section(detector: MarkerDetector) -> None:
    text = "[a]\nlicense =\n[b]\nlicense = Apache-2.0\n"
    result = detector._detect_structured_format(text, ".ini")
    assert _summary(result) == [("Apache-2.0", 1.0)]


def test_ini_default_section_inherited_by_first_section(
    detector: MarkerDetector,
) -> None:
    """Quirk: [DEFAULT] is not a section, but its keys are inherited by
    every real section, so the first section reports it."""
    text = "[DEFAULT]\nlicense = MIT\n[a]\nname = x\n"
    result = detector._detect_structured_format(text, ".ini")
    assert _summary(result) == [("MIT", 1.0)]


def test_ini_sections_without_license_return_nothing(
    detector: MarkerDetector,
) -> None:
    assert not detector._detect_structured_format("[a]\nname = x\n[b]\nk = v\n", ".ini")


def test_ini_unresolvable_first_section_does_not_hide_later_one(
    detector: MarkerDetector,
) -> None:
    """Regression: a first-section license value that resolves to nothing
    must not stop the scan; the next section's valid license is used."""
    text = "[a]\nlicense = see LICENSE file\n[b]\nlicense = MIT\n"
    result = detector._detect_structured_format(text, ".ini")
    assert _summary(result) == [("MIT", 1.0)]


def test_ini_bad_interpolation_in_one_section_does_not_hide_the_next(
    detector: MarkerDetector,
) -> None:
    text = "[a]\nlicense = 100% free\n[b]\nlicense = MIT\n"
    result = detector._detect_structured_format(text, ".ini")
    assert _summary(result) == [("MIT", 1.0)]


def test_ini_unrecognised_license_text_is_not_a_candidate(
    detector: MarkerDetector,
) -> None:
    """Regression: free text after 'license' must not become a phantom
    is_spdx candidate."""
    text = "[docs]\nlicense: see LICENSE file\n"
    assert not detector._detect_structured_format(text, ".ini")
    assert not detector._detect_structured_format(text)


@pytest.mark.parametrize(
    "text",
    [
        "license = MIT\n",
        "[a]\nlicense = MIT\nlicense = Apache-2.0\n",
        "[a]\nlicense = 100% free\n",
    ],
    ids=["no_section_header", "duplicate_option", "percent_interpolation"],
)
def test_ini_malformed_returns_nothing_without_raising(
    detector: MarkerDetector, text: str
) -> None:
    assert not detector._detect_structured_format(text, ".ini")


def test_ini_ignores_toml_table_under_cfg_ext(detector: MarkerDetector) -> None:
    """TOML parsing is gated to .toml/no-ext, so .cfg never runs it."""
    text = 'license = {text = "MIT"}'
    assert not detector._detect_structured_format(text, ".cfg")


# --- extension gating ---


@pytest.mark.parametrize("ext", [".yaml", ".txt", ".md"])
def test_unknown_extension_returns_nothing(detector: MarkerDetector, ext: str) -> None:
    for text in ('license = {text = "MIT"}', "[a]\nlicense = MIT\n"):
        assert not detector._detect_structured_format(text, ext)


# --- no extension: TOML then INI both run ---


def test_no_ext_toml_table_resolves(detector: MarkerDetector) -> None:
    result = detector._detect_structured_format('license = {text = "MIT"}')
    assert _summary(result) == [("MIT", 1.0)]


def test_no_ext_ini_resolves(detector: MarkerDetector) -> None:
    text = "# setup\n[metadata]\nlicense = MIT\n"
    result = detector._detect_structured_format(text)
    assert _summary(result) == [("MIT", 1.0)]


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
