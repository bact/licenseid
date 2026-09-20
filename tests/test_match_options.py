# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""match() rejects an option it does not know, whatever else it was given:
a mistyped or removed option must not pass with no effect."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from conftest import MIT_SEARCH_TEXT, make_mit_db_path

from licenseid.errors import InvalidInputError, LicenseIdError
from licenseid.matcher import _MATCH_OPTIONS, AggregatedLicenseMatcher
from licenseid.types import MatchRequest

# One valid value per option. Kept beside MatchRequest by the test below, so
# a new option cannot be added without deciding whether match() takes it.
VALID_OPTIONS: dict[str, Any] = {
    "enable_popularity": True,
    "exclude": ["Apache-2.0"],
    "hint": ["MIT"],
    "only_common": False,
    "only_spdx": False,
}


@pytest.fixture
def matcher() -> Generator[AggregatedLicenseMatcher, None, None]:
    db_path, keep_alive = make_mit_db_path(
        "test_match_options", datetime.now(timezone.utc).isoformat()
    )
    yield AggregatedLicenseMatcher(db_path)
    keep_alive.close()


def test_every_match_request_option_is_covered() -> None:
    named_parameters = {"text", "license_id", "file_path"}
    assert set(VALID_OPTIONS) == set(MatchRequest.__annotations__) - named_parameters
    assert set(VALID_OPTIONS) == _MATCH_OPTIONS


@pytest.mark.parametrize("name", sorted(VALID_OPTIONS))
def test_a_known_option_is_accepted(
    matcher: AggregatedLicenseMatcher, name: str
) -> None:
    assert matcher.match(text=MIT_SEARCH_TEXT, **{name: VALID_OPTIONS[name]})


@pytest.mark.parametrize(
    "name", ["enable_popularty", "enable_java", "ONLY_SPDX", "only-spdx", "", "text2"]
)
def test_an_unknown_option_is_rejected(
    matcher: AggregatedLicenseMatcher, name: str
) -> None:
    options: dict[str, Any] = {name: True}
    with pytest.raises(InvalidInputError) as raised:
        matcher.match(text=MIT_SEARCH_TEXT, **options)
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
    matcher: AggregatedLicenseMatcher, kwargs: dict[str, Any]
) -> None:
    """The early returns (an explicit ID, empty text) and a file that cannot
    be read must not let a bad option through, or change the error."""
    with pytest.raises(InvalidInputError, match="option: invalid: 'bogus'"):
        matcher.match(bogus=1, **kwargs)


def test_every_unknown_option_is_named_once_in_order(
    matcher: AggregatedLicenseMatcher,
) -> None:
    with pytest.raises(InvalidInputError) as raised:
        matcher.match(text=MIT_SEARCH_TEXT, only_spdx=True, zed=1, alpha=2)
    assert str(raised.value).startswith("option: invalid: 'alpha', 'zed'; use one of")
    assert "only_spdx'" not in str(raised.value).split(";")[0]


def test_the_error_is_a_licenseid_error_and_a_runtime_error(
    matcher: AggregatedLicenseMatcher,
) -> None:
    with pytest.raises(LicenseIdError):
        matcher.match(text=MIT_SEARCH_TEXT, bogus=1)
    with pytest.raises(RuntimeError):
        matcher.match(text=MIT_SEARCH_TEXT, bogus=1)


def test_a_rejected_call_leaves_the_matcher_usable(
    matcher: AggregatedLicenseMatcher,
) -> None:
    plain = matcher.match(text=MIT_SEARCH_TEXT)
    with pytest.raises(InvalidInputError):
        matcher.match(text=MIT_SEARCH_TEXT, bogus=1)
    assert matcher.match(text=MIT_SEARCH_TEXT) == plain


def test_a_valid_option_does_not_change_the_result_when_it_is_the_default(
    matcher: AggregatedLicenseMatcher,
) -> None:
    assert matcher.match(text=MIT_SEARCH_TEXT, only_spdx=True) == matcher.match(
        text=MIT_SEARCH_TEXT
    )
