# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""detect() rejects an option it does not know, whatever else it was given:
a mistyped or removed option must not pass with no effect."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from conftest import MIT_SEARCH_TEXT, make_mit_db_path

from licenseid.detector import _MATCH_OPTIONS, LicenseDetector
from licenseid.errors import InvalidInputError, LicenseIdError
from licenseid.types import DetectRequest

# One valid value per option. Kept beside DetectRequest by the test below, so
# a new option cannot be added without deciding whether detect() takes it.
VALID_OPTIONS: dict[str, Any] = {
    "enable_popularity": True,
    "exclude": ["Apache-2.0"],
    "hint": ["MIT"],
    "only_common": False,
    "only_spdx": False,
}


@pytest.fixture
def matcher() -> Generator[LicenseDetector, None, None]:
    db_path, keep_alive = make_mit_db_path(
        "test_match_options", datetime.now(timezone.utc).isoformat()
    )
    yield LicenseDetector(db_path)
    keep_alive.close()


def test_every_match_request_option_is_covered() -> None:
    named_parameters = {"text", "license_id", "file_path"}
    assert set(VALID_OPTIONS) == set(DetectRequest.__annotations__) - named_parameters
    assert set(VALID_OPTIONS) == _MATCH_OPTIONS


@pytest.mark.parametrize("name", sorted(VALID_OPTIONS))
def test_a_known_option_is_accepted(matcher: LicenseDetector, name: str) -> None:
    assert matcher.detect(text=MIT_SEARCH_TEXT, **{name: VALID_OPTIONS[name]})


@pytest.mark.parametrize(
    "name", ["enable_popularty", "enable_java", "ONLY_SPDX", "only-spdx", "", "text2"]
)
def test_an_unknown_option_is_rejected(matcher: LicenseDetector, name: str) -> None:
    options: dict[str, Any] = {name: True}
    with pytest.raises(InvalidInputError) as raised:
        matcher.detect(text=MIT_SEARCH_TEXT, **options)
    assert str(raised.value).startswith(f"option: invalid: {name!r}; use one of ")
    assert "\n" not in str(raised.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"license_id": "MIT"},
        {"text": ""},
        {"text": None},
        {},
        {"file_path": "/no/such/file"},
    ],
    ids=["license_id", "empty_text", "no_text", "no_input", "missing_file"],
)
def test_the_option_is_checked_before_any_input(
    matcher: LicenseDetector, kwargs: dict[str, Any]
) -> None:
    """The early returns (an explicit ID, empty text) and a file that cannot
    be read must not let a bad option through, or change the error."""
    with pytest.raises(InvalidInputError, match="option: invalid: 'bogus'"):
        matcher.detect(bogus=1, **kwargs)


def test_every_unknown_option_is_named_once_in_order(
    matcher: LicenseDetector,
) -> None:
    """Enough names that a set's arbitrary order would show (the hash seed
    varies between runs), and the known options listed in a fixed order."""
    unknown = ["zed", "yak", "xor", "wax", "vim", "urn", "tab", "sun", "ark"]
    options: dict[str, Any] = {name: 1 for name in unknown}
    with pytest.raises(InvalidInputError) as raised:
        matcher.detect(text=MIT_SEARCH_TEXT, only_spdx=True, **options)
    named = ", ".join(repr(name) for name in sorted(unknown))
    known = ", ".join(sorted(VALID_OPTIONS))
    assert str(raised.value) == f"option: invalid: {named}; use one of {known}"


def test_the_error_is_a_licenseid_error_and_a_runtime_error(
    matcher: LicenseDetector,
) -> None:
    with pytest.raises(LicenseIdError):
        matcher.detect(text=MIT_SEARCH_TEXT, bogus=1)
    with pytest.raises(RuntimeError):
        matcher.detect(text=MIT_SEARCH_TEXT, bogus=1)


def test_a_rejected_call_leaves_the_matcher_usable(
    matcher: LicenseDetector,
) -> None:
    plain = matcher.detect(text=MIT_SEARCH_TEXT)
    with pytest.raises(InvalidInputError):
        matcher.detect(text=MIT_SEARCH_TEXT, bogus=1)
    assert matcher.detect(text=MIT_SEARCH_TEXT) == plain


def test_a_valid_option_does_not_change_the_result_when_it_is_the_default(
    matcher: LicenseDetector,
) -> None:
    assert matcher.detect(text=MIT_SEARCH_TEXT, only_spdx=True) == matcher.detect(
        text=MIT_SEARCH_TEXT
    )
