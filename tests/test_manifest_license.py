# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The license field of a package manifest, end to end, and the SPDX flags
on every result. Roadmap item 18."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import time
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import MIT_SEARCH_TEXT, json_lines
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.manifest import license_value_groups, toml_license_values
from licenseid.matcher import AggregatedLicenseMatcher

FILLER = (
    "A widget scheduler that keeps a queue of pending widgets and dispatches"
    " them to worker threads in arrival order, retrying transient failures a"
    " few times before giving up and reporting an error to the caller"
)

# A small manifest has fewer than 30 words, the Tier 0 threshold; FILLER
# takes each past it.
MANIFESTS: dict[str, tuple[str, str]] = {
    "package-json": (
        "package.json",
        '{{"name": "x", "version": "1.0.0", {extra}"license": "{value}"}}',
    ),
    "pyproject-table": (
        "pyproject.toml",
        '[project]\nname = "x"\n{extra}license = {{text = "{value}"}}\n',
    ),
    "pyproject-string": (
        "pyproject.toml",
        '[project]\nname = "x"\n{extra}license = "{value}"\n',
    ),
    "poetry": (
        "pyproject.toml",
        '[tool.poetry]\nname = "x"\n{extra}license = "{value}"\n',
    ),
    "cargo": (
        "Cargo.toml",
        '[package]\nname = "x"\nedition = "2021"\n{extra}license = "{value}"\n',
    ),
    "setup-cfg": ("setup.cfg", "[metadata]\nname = x\n{extra}license = {value}\n"),
}


def extra_field(kind: str) -> str:
    if kind == "package-json":
        return f'"description": "{FILLER}", '
    if kind == "setup-cfg":
        return f"description = {FILLER}\n"
    return f'description = "{FILLER}"\n'


def manifest(tmp_path: Path, kind: str, value: str, large: bool) -> str:
    name, template = MANIFESTS[kind]
    extra = extra_field(kind) if large else ""
    path = tmp_path / name
    path.write_text(template.format(extra=extra, value=value), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    rows = [
        Lic("MIT", "MIT License", True, True, True, search_text=MIT_SEARCH_TEXT),
        Lic("Apache-2.0", "Apache License 2.0", True, True, True, search_text="x"),
        Lic("Apache-1.0", "Apache License 1.0", True, False, True, search_text="y"),
        Lic("0BSD", "BSD Zero Clause License", True, True, False),
        *GPL2_ROWS,
        Lic(
            "GPL-2.0-with-GCC-exception",
            "GNU General Public License v2.0 w/GCC Runtime Library exception",
            is_deprecated=True,
        ),
    ]
    yield from seeded_db("test_manifest_license", rows, ["GCC-exception-2.0"])


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", list(MANIFESTS))
def test_a_manifest_expression_is_certain(
    db: str, tmp_path: Path, kind: str, large: bool
) -> None:
    """A small manifest used to be matched by name (Apache-1.0 at 1.01); a
    TOML or INI field scored 0.902 with no flags, so is_spdx() said False."""
    path = manifest(tmp_path, kind, "MIT OR Apache-2.0", large)
    matcher = AggregatedLicenseMatcher(db)
    top = matcher.match(file_path=path)[0]
    assert (top["license_id"], top["score"]) == ("Apache-2.0 OR MIT", 1.0)
    # OSI and FSF approval has no plain meaning for an OR (flag_source).
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        False,
        False,
    )
    assert matcher.is_spdx(file_path=path)


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", list(MANIFESTS))
def test_a_manifest_license_id_carries_its_flags(
    db: str, tmp_path: Path, kind: str, large: bool
) -> None:
    path = manifest(tmp_path, kind, "Apache-2.0", large)
    matcher = AggregatedLicenseMatcher(db)
    top = matcher.match(file_path=path)[0]
    assert (top["license_id"], top["score"]) == ("Apache-2.0", 1.0)
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        True,
        True,
    )
    assert matcher.is_osi(file_path=path)
    assert matcher.is_fsf(file_path=path)


FLAGS = ("is_spdx", "is_osi_approved", "is_fsf_libre")


@pytest.mark.parametrize(
    "text",
    [
        "MIT",  # Tier 0, an ID
        "MIT License",  # Tier 0, a name
        MIT_SEARCH_TEXT,  # Tier 2, the license text
    ],
    ids=["id", "name", "text"],
)
def test_every_result_carries_the_flags(db: str, text: str) -> None:
    results = AggregatedLicenseMatcher(db).match(text=text)
    assert results
    for result in results:
        assert all(isinstance(result.get(flag), bool) for flag in FLAGS), result
    assert results[0]["license_id"] == "MIT"
    assert all(results[0].get(flag) for flag in FLAGS)


@pytest.mark.parametrize(
    ("deprecated", "replacement"),
    [
        ("GPL-2.0", "GPL-2.0-only"),
        ("GPL-2.0-with-GCC-exception", "GPL-2.0-only WITH GCC-exception-2.0"),
    ],
    ids=["to-id", "to-expression"],
)
def test_a_deprecated_id_takes_the_flags_of_its_replacement(
    db: str, deprecated: str, replacement: str
) -> None:
    """A deprecated ID answers its replacement, a license row or an
    expression: the flags are the replacement's, not the deprecated row's
    nor "unknown"."""
    matcher = AggregatedLicenseMatcher(db)
    top = matcher.match(text=deprecated)[0]
    assert top["license_id"] == replacement
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        True,
        True,
    )
    assert matcher.is_spdx(deprecated)
    assert matcher.is_osi(deprecated)


def test_match_json_shows_the_flags_of_a_manifest(db: str, tmp_path: Path) -> None:
    path = manifest(tmp_path, "pyproject-string", "MIT OR Apache-2.0", large=False)
    result = CliRunner().invoke(cli, ["--db", db, "match", "--json", path])
    assert result.exit_code == 0, result.output
    top = json_lines(result.stdout)[0]
    assert {flag: top[flag] for flag in FLAGS} == {
        "is_spdx": True,
        "is_osi_approved": False,
        "is_fsf_libre": False,
    }


def test_is_spdx_answers_yes_for_a_toml_expression(db: str, tmp_path: Path) -> None:
    """It answered false: the field scored 0.902, with no flags."""
    path = manifest(tmp_path, "pyproject-table", "MIT OR Apache-2.0", large=True)
    result = CliRunner().invoke(cli, ["--db", db, "is-spdx", path])
    assert (result.exit_code, result.stdout) == (0, "true\n")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            (
                '[project]\nlicense = "A"\nlicense = "B"\n'
                '[package]\nlicense = "C"\n[project]\nlicense = "D"\n'
            ),
            ["A", "C"],
        ),
        ('[a]\nlicense = {text = "A"}\n[b]\nlicense = {text = "B"}\n', ["A"]),
        ('[project]\nlicense = "MIT/Apache-2.0"\n', ["MIT/Apache-2.0"]),
        ('[package]\nlicense = "MIT/Apache-2.0"\n', ["MIT OR Apache-2.0"]),
    ],
    ids=["string-forms", "table-forms", "slash-elsewhere", "slash-in-cargo"],
)
def test_a_manifest_declares_one_license_per_table(
    text: str, expected: list[str]
) -> None:
    """Each value costs a database lookup, so a file of thousands of license
    lines yields one value per form and table. Only Cargo spells OR with a
    slash."""
    assert toml_license_values(text) == expected


@pytest.mark.parametrize("large", [False, True], ids=["small", "large"])
@pytest.mark.parametrize("kind", ["package-json", "cargo", "setup-cfg"])
def test_a_loosely_named_license_is_matched_on_its_own(
    db: str, tmp_path: Path, kind: str, large: bool
) -> None:
    """ "Apache 2.0" is no ID or expression, but names Apache-2.0 exactly. The
    small file used to be matched by name as a whole: Apache-1.0 at 1.01."""
    path = manifest(tmp_path, kind, "Apache 2.0", large)
    top = AggregatedLicenseMatcher(db).match(file_path=path)[0]
    assert top["license_id"] == "Apache-2.0"
    assert top["is_spdx"] and top["is_osi_approved"]


@pytest.mark.parametrize(
    "value",
    # "Apache" is also every word of "Apache License 1.0" in the small file,
    # which is how the whole file was matched by name: Apache-1.0 at 1.01.
    ["Apache", "BSD", "UNLICENSED", "SEE LICENSE IN LICENSE.txt", "Proprietary"],
)
@pytest.mark.parametrize("kind", ["package-json", "cargo"])
def test_a_small_manifest_naming_no_license_has_no_answer(
    db: str, tmp_path: Path, kind: str, value: str
) -> None:
    """Not a name match of the whole file, and not a fuzzy one of the value:
    "BSD" is a fuzzy match for 0BSD."""
    path = manifest(tmp_path, kind, value, large=False)
    assert AggregatedLicenseMatcher(db).match(file_path=path) == []


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("package.json", '{"name": "apache", "version": "1.0.0"}'),
        ("package.json", '{"name": "apache", "license": ""}'),
        ("composer.json", '{"name": "apache", "license": ["MIT", "Apache-2.0"]}'),
        ("Cargo.toml", '[package]\nname = "apache"\nlicense-file = "LICENSE"\n'),
        ("pyproject.toml", '[project]\nname = "apache"\nlicense = {file = "L"}\n'),
        ("setup.cfg", "[metadata]\nname = apache\n"),
        ("", '{"name": "apache", "license": ""}'),
        ("", '[package]\nname = "apache"\nlicense-file = "LICENSE"\n'),
    ],
    ids=[
        "no-field",
        "empty",
        "array",
        "license-file",
        "file-table",
        "setup-cfg",
        "text-json",
        "text-toml",
    ],
)
def test_a_small_manifest_with_no_license_value_has_no_answer(
    db: str, tmp_path: Path, name: str, text: str
) -> None:
    """The crate name "zlib-rs" answered Zlib at 1.01 when the field was
    missing; a manifest is never matched by name as a whole."""
    matcher = AggregatedLicenseMatcher(db)
    if name:
        (tmp_path / name).write_text(text, encoding="utf-8")
        assert matcher.match(file_path=str(tmp_path / name)) == []
    else:
        assert matcher.match(text=text) == []


@pytest.mark.parametrize(
    "text", ["[MIT]", "[MIT](LICENSE)", "[MIT License]", '["MIT"]']
)
def test_a_bracketed_name_is_no_manifest(db: str, text: str) -> None:
    """Text that starts with [x] reads as an INI section, a TOML table or a
    JSON array, but with no key in it, it is no manifest: Tier 0 still
    answers."""
    assert AggregatedLicenseMatcher(db).match(text=text)[0]["license_id"] == "MIT"


@pytest.mark.parametrize(
    ("kind", "value", "expected"),
    [
        # Cargo's old spelling of OR.
        ("cargo", "MIT/Apache-2.0", "Apache-2.0 OR MIT"),
        ("cargo", "MIT / Apache-2.0", "Apache-2.0 OR MIT"),
        # A slash that is not between two IDs is not an OR.
        ("cargo", "https://spdx.org/licenses/MIT", "MIT"),
        # The SPDX License List's own page for a license.
        ("package-json", "https://spdx.org/licenses/MIT.html", "MIT"),
        ("cargo", "https://spdx.org/licenses/Apache-2.0.html", "Apache-2.0"),
        # A grant after the expression is the only thing that may follow it.
        ("package-json", "GPL-2.0 or later", "GPL-2.0-or-later"),
    ],
)
def test_a_manifest_value_is_read_whole(
    db: str, tmp_path: Path, kind: str, value: str, expected: str
) -> None:
    path = manifest(tmp_path, kind, value, large=False)
    top = AggregatedLicenseMatcher(db).match(file_path=path)[0]
    assert (top["license_id"], top["score"]) == (expected, 1.0)


@pytest.mark.parametrize("kind", ["package-json", "pyproject-string"])
def test_a_slash_elsewhere_is_not_or(db: str, tmp_path: Path, kind: str) -> None:
    """Only Cargo spells OR with a slash; elsewhere it is no expression, and
    answering the MIT before it would drop a license."""
    path = manifest(tmp_path, kind, "MIT/Apache-2.0", large=True)
    results = AggregatedLicenseMatcher(db).match(file_path=path)
    assert all(r["license_id"] != "MIT" or r["score"] < 0.85 for r in results)


def test_a_name_match_needs_no_lookup_per_result(db: str) -> None:
    """Tier 0 takes the flags from its cached name table: a broad name
    returns dozens of results, and a lookup each made it 20 times slower."""
    matcher = AggregatedLicenseMatcher(db)
    matcher.match(text="warm up the name cache")
    with mock.patch.object(
        LicenseDatabase,
        "get_license_details",
        autospec=True,
        wraps=LicenseDatabase.get_license_details,
    ) as lookup:
        results = matcher.match(text="Apache License")
    assert len(results) >= 2
    assert all(isinstance(r.get("is_spdx"), bool) for r in results)
    assert lookup.call_count == 0


def test_a_small_package_json_in_npm_object_form(db: str, tmp_path: Path) -> None:
    """The old object form was not read, so the file was matched by name:
    Apache-1.0 at 1.01."""
    path = tmp_path / "package.json"
    path.write_text(
        '{"name": "x", "version": "1.0.0", "license": '
        '{"type": "Apache-2.0", "url": "https://www.apache.org/licenses/"}}',
        encoding="utf-8",
    )
    top = AggregatedLicenseMatcher(db).match(file_path=str(path))[0]
    assert (top["license_id"], top["score"]) == ("Apache-2.0", 1.0)


@pytest.mark.parametrize("first_line", ["# Usage", "[![PyPI](https://x)](https://y)"])
@pytest.mark.parametrize("field", ['license = "MIT"', 'license = {text = "MIT"}'])
def test_a_readme_with_a_toml_example_is_not_answered_from_it(
    db: str, first_line: str, field: str
) -> None:
    """Piped text has no file name, so it is tried as TOML; the example
    names the reader's license, not this file's. A badge line starts with a
    bracket too."""
    text = (
        f"{first_line}\nSet the license in your own pyproject.toml, for example:"
        f"\n\n```toml\n[project]\n{field}\n```\n\n{FILLER}"
    )
    results = AggregatedLicenseMatcher(db).match(text=text)
    assert not results or results[0]["score"] < 1.0


def test_a_small_pyproject_with_a_license_sub_table(db: str, tmp_path: Path) -> None:
    """[project.license] with text = "..." is PEP 621's table written out;
    unread, the file was matched by name: Apache-1.0 at 1.01."""
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[project]\nname = "x"\nversion = "1.0.0"\n\n'
        '[project.license]\ntext = "MIT OR Apache-2.0"\n',
        encoding="utf-8",
    )
    top = AggregatedLicenseMatcher(db).match(file_path=str(path))[0]
    assert (top["license_id"], top["score"]) == ("Apache-2.0 OR MIT", 1.0)


def test_a_manifest_is_parsed_once_per_match(db: str, tmp_path: Path) -> None:
    path = manifest(tmp_path, "package-json", "Apache 2.0", large=True)
    with (
        mock.patch(
            "licenseid.matcher.license_value_groups",
            autospec=True,
            wraps=license_value_groups,
        ) as in_matcher,
        mock.patch(
            "licenseid.markers.license_value_groups",
            autospec=True,
            wraps=license_value_groups,
        ) as in_markers,
    ):
        AggregatedLicenseMatcher(db).match(file_path=path)
    assert in_matcher.call_count + in_markers.call_count == 1


_RUN = 50_000


@pytest.mark.parametrize(
    "text",
    [
        "[" + " " * _RUN,
        "[[" + "a" * _RUN + "]",
        "[project]\nlicense" + " " * _RUN + "x",  # 9 s in configparser on 3.10
        "[project]\nlicense" + "\u00a0\t" * _RUN + "x",
        '[project]\nlicense = "' + "a" * _RUN,
        '[project]\nlicense = "MIT"' + " " * _RUN + "x",
        '[package]\nlicense = "' + "a/" * _RUN + '"',
        "license = {text" + " " * _RUN,
        "[a]\n" * _RUN,
        '[a]\nx = """' + '\\"""' * _RUN,  # every delimiter escaped
        "[a]\nx = " + '"a" ' * _RUN,
    ],
    ids=[
        "open-header",
        "open-array",
        "key-space-run",
        "key-unicode-space-run",
        "open-string",
        "trailing-space-run",
        "slashes",
        "open-table-form",
        "many-headers",
        "escaped-delimiters",
        "one-line-strings",
    ],
)
def test_a_long_run_reads_in_linear_time(text: str) -> None:
    """Every reader on an extensionless input, which tries each format.
    Each takes a few milliseconds; the limit leaves CI headroom."""
    start = time.monotonic()
    license_value_groups(text, "")
    assert time.monotonic() - start < 0.5
