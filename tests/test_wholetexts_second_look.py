# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The second look of the ``TEXTS`` search (``_Search._widened``): when it
runs, how far it widens a span, and that a hit with no long gap gets none.

``LONG`` is the 400-word text of ``test_wholetexts_gap``."""
# pylint: disable=missing-function-docstring,protected-access

import pytest
from test_wholetexts import fake
from test_wholetexts_gap import CORPUS, LONG, LONG_WORDS

from licenseid import wholetexts
from licenseid.textlocate import Alignment, Budget, align
from licenseid.wholetexts import found_rows


def _search() -> tuple[wholetexts._Search, wholetexts._Item]:
    """A search over ``LONG`` as the input (400 words) and its one item."""
    source = wholetexts._read_input(LONG, CORPUS)
    assert source is not None
    budget = Budget()
    items = wholetexts._items(CORPUS, source, None, budget)
    return wholetexts._Search(source, items, budget), items[0]


def _widened(
    span: tuple[int, int], missing: tuple[int, int], trimmed: tuple[int, int]
) -> tuple[int, int] | None:
    search, item = _search()
    search._found[item.serial] = Alignment(span[0], span[1], (missing,), trimmed)
    return search._widened(item, span)


@pytest.mark.parametrize(
    ("trimmed", "expected"),
    [(15, (70, 380)), (14, None)],
    ids=["half", "under-half"],
)
def test_the_front_run_is_looked_for_when_trimmed_blocks_matched_half(
    trimmed: int, expected: tuple[int, int] | None
) -> None:
    # A run of 30 words missing at the front: 15 matched words trimmed off
    # it are half, 14 are less.
    assert _widened((100, 380), (0, 30), (trimmed, 0)) == expected


@pytest.mark.parametrize(
    ("trimmed", "expected"),
    [(15, (100, 350)), (14, None)],
    ids=["half", "under-half"],
)
def test_the_back_run_is_looked_for_when_trimmed_blocks_matched_half(
    trimmed: int, expected: tuple[int, int] | None
) -> None:
    # The last 30 of 400 words missing: the span (100, 320) widens to 350.
    assert _widened((100, 320), (370, 400), (0, trimmed)) == expected


def test_the_widened_start_is_not_below_the_input() -> None:
    # A far copy less than one run from the input's start: 10 words before
    # the span, 30 missing. A start of -20 would slice from the input's end.
    assert _widened((10, 380), (0, 30), (20, 0)) == (0, 380)


def test_the_widened_end_is_not_past_the_input() -> None:
    assert _widened((100, 390), (370, 400), (0, 20)) == (100, 400)


def test_a_hit_with_no_long_gap_gets_no_second_alignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The first 10 words sit before 50 foreign words, the next 10 are lost:
    # the front is trimmed and 20 words (99 characters) are missing, a run
    # that may be widened, but is under 150 characters: one alignment.
    calls: list[str] = []

    def counted(text: str, window: str) -> Alignment | None:
        calls.append(text)
        return align(text, window)

    monkeypatch.setattr(wholetexts, "align", counted)
    words = [*LONG_WORDS[:10], *fake(5, 50).split(), *LONG_WORDS[20:]]
    assert found_rows(" ".join(words), CORPUS, "Z") == ["T"]
    assert len(calls) == 1
