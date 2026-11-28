# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``textcorpus``: tokens, word codes and the immutable corpus."""
# pylint: disable=missing-function-docstring

import dataclasses

import pytest

from licenseid import textcorpus
from licenseid.textcorpus import (
    UNKNOWN,
    TextCorpus,
    TextRow,
    VarRegion,
    critical_counts,
    input_tokens,
)
from licenseid.textgrams import split_words

_TEXT = "alpha beta gamma delta epsilon"


def _row(license_id: str, text: str, core: str | None = None) -> TextRow:
    return TextRow(license_id, text, core, (license_id,))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mit  licence\tnow", ["mit", "licence", "now"]),
        ("許諾 書", ["許", "諾", "書"]),
        ("ライセンス", ["ラ", "イ", "セ", "ン", "ス"]),
        ("see 許諾 ok", ["see", "許", "諾", "ok"]),
        ("abc許諾def", ["abc", "許", "諾", "def"]),
        ("café au lait", ["café", "au", "lait"]),
        ("라이선스 조건", ["라이선스", "조건"]),
    ],
)
def test_split_words(text: str, expected: list[str]) -> None:
    assert split_words(text) == expected


def test_ascii_input_has_no_offsets() -> None:
    assert input_tokens("one two  three", 10) == (["one", "two", "three"], None)


def test_non_ascii_offsets_slice_the_input() -> None:
    text = "see 許諾 café"
    words, spans = input_tokens(text, 10)
    assert spans is not None
    assert [text[start:end] for start, end in spans] == words
    assert words == ["see", "許", "諾", "café"]


def test_counting_stops_one_past_the_limit() -> None:
    words, spans = input_tokens("許" * 100, 10)
    assert len(words) == 11
    assert spans is not None and len(spans) == 11


def test_ascii_input_is_never_cut() -> None:
    assert len(input_tokens("a " * 100, 10)[0]) == 100


def test_critical_counts_follow_the_fixed_order() -> None:
    words = ["not", "this", "unless", "not", "that", "except"]
    counts = dict(zip(textcorpus.CRITICAL_ORDER, critical_counts(words)))
    assert counts == {"except": 1, "irrevocable": 0, "not": 2, "unless": 1}


@pytest.mark.parametrize(
    ("reworded", "negations"),
    [
        ("the names of its contributors may not be used", 1),
        ("neither the name nor the names of its contributors may be used", 1),
        ("the names of its contributors may be used", 0),
        ("neither the name nor the names may not be used", 2),
    ],
)
def test_neither_counts_as_not(reworded: str, negations: int) -> None:
    counts = dict(zip(textcorpus.CRITICAL_ORDER, critical_counts(reworded.split())))
    assert counts == {"except": 0, "irrevocable": 0, "not": negations, "unless": 0}


def test_twins_are_one_entry_named_by_the_least_id() -> None:
    group = ("Z-or-later", "Z-only")
    corpus = TextCorpus.build(
        [
            TextRow("Z-or-later", _TEXT, None, group),
            TextRow("Z-only", _TEXT, None, group),
        ]
    )
    assert len(corpus.entries) == 1
    assert corpus.entries[0].text.row_id == "Z-only"
    assert corpus.representative("Z-or-later") == "Z-only"
    assert corpus.representative("Z-only") == "Z-only"
    assert corpus.representative("Other") is None


def test_a_group_member_without_a_row_is_named_too() -> None:
    corpus = TextCorpus.build([TextRow("B-1", _TEXT, None, ("A-1", "B-1"))])
    assert corpus.entries[0].text.row_id == "A-1"
    assert corpus.representative("B-1") == "A-1"


def test_an_empty_text_is_not_in_the_corpus() -> None:
    corpus = TextCorpus.build([_row("Empty", ""), _row("Full", _TEXT)])
    assert [entry.text.row_id for entry in corpus.entries] == ["Full"]
    assert corpus.representative("Empty") is None


@pytest.mark.parametrize("core", [None, "", _TEXT])
def test_no_core_unless_it_differs(core: str | None) -> None:
    corpus = TextCorpus.build([_row("A", _TEXT, core)])
    assert corpus.entries[0].core is None


def test_the_core_is_coded_at_build_time() -> None:
    corpus = TextCorpus.build([_row("A", _TEXT, "alpha beta zeta")])
    core = corpus.entries[0].core
    assert core is not None and core.is_core and core.row_id == "A"
    assert core.codes == corpus.encode(["alpha", "beta", "zeta"])
    assert UNKNOWN not in core.codes
    assert "zeta" in corpus.vocabulary


def test_codes_are_one_per_token_and_shared() -> None:
    corpus = TextCorpus.build([_row("A", _TEXT), _row("B", "delta alpha 許")])
    first, second = (entry.text for entry in corpus.entries)
    assert len(first.codes) == 5 and len(second.codes) == 3
    assert second.codes[1] == first.codes[0]
    assert len(set(first.codes)) == 5
    assert all(not 0xD800 <= ord(code) <= 0xDFFF for code in corpus.vocabulary.values())


def test_an_unknown_word_codes_as_unknown() -> None:
    corpus = TextCorpus.build([_row("A", _TEXT)])
    codes = corpus.encode(["alpha", "omega"])
    assert codes[1] == UNKNOWN and codes[0] != UNKNOWN


def test_text_carries_its_critical_counts() -> None:
    corpus = TextCorpus.build([_row("A", "do not copy unless not")])
    counts = dict(zip(textcorpus.CRITICAL_ORDER, corpus.entries[0].text.critical))
    assert counts["not"] == 2 and counts["unless"] == 1


@pytest.mark.parametrize(
    ("number", "code"),
    [(1, 0x1), (0xD7FF, 0xD7FF), (0xD800, 0xE000), (0x10F7FF, 0x10FFFF)],
)
def test_word_numbers_skip_the_surrogates(number: int, code: int) -> None:
    assert textcorpus.word_code(number) == chr(code)


def test_numbers_past_the_last_share_the_last_code() -> None:
    last = textcorpus.word_code(0x10F7FF)
    assert textcorpus.word_code(0x10F800) == last


def test_the_corpus_cannot_change() -> None:
    corpus = TextCorpus.build([_row("A", _TEXT)])
    with pytest.raises(dataclasses.FrozenInstanceError):
        corpus.entries = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        corpus.vocabulary["new"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        corpus.representatives["new"] = "x"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        corpus.entries[0].text.codes = ""  # type: ignore[misc]


@pytest.mark.parametrize(
    ("text", "regions", "least"),
    [
        ("aa bb cccc ddddd eeeeee", (), 23),
        ("aa bb cccc ddddd eeeeee", (VarRegion(1, 2, ".+"),), 20),
        ("aa bb cccc ddddd eeeeee", (VarRegion(0, 1, ".+"),), 20),
        ("aa bb cccc ddddd eeeeee", (VarRegion(4, 5, ".+"),), 16),
        (
            "aa bb cccc ddddd eeeeee",
            (VarRegion(1, 3, ".+"), VarRegion(2, 4, ".+")),
            9,
        ),
        (
            "aa bb cccc ddddd eeeeee",
            (VarRegion(1, 2, ".+"), VarRegion(2, 3, ".+")),
            15,
        ),
        ("aa bb cccc ddddd eeeeee", (VarRegion(0, 5, ".*"),), 0),
        ("aa bb cccc ddddd eeeeee", (VarRegion(2, 2, ".*"),), 23),
        (
            "aa bb cccc ddddd eeeeee",
            (VarRegion(0, 2, ".*"), VarRegion(1, 2, ".+"), VarRegion(3, 4, ".+")),
            11,
        ),
        ("\u8a31\u53ef\u8b49\u66f8", (VarRegion(1, 2, ".+"),), 4),
        (
            "\u8a31\u53ef\u8b49\u66f8",
            (VarRegion(1, 2, ".+"), VarRegion(2, 3, ".+")),
            3,
        ),
        ("\u8a31\u53ef\u8b49\u66f8", (VarRegion(2, 2, ".*"),), 4),
    ],
    ids=[
        "none",
        "middle",
        "start",
        "end",
        "overlapping",
        "touching",
        "every-token",
        "point",
        "nested",
        "han",
        "han-touching",
        "han-point",
    ],
)
def test_least_is_the_text_with_its_variable_parts_cut(
    text: str, regions: tuple[VarRegion, ...], least: int
) -> None:
    """The characters ``textmask`` keeps of *text* with each run of
    variable parts cut out and the pieces left joined by one space: a run
    in the middle also takes one of its two spaces; between Han tokens the
    joining space adds one (4 of 4)."""
    corpus = TextCorpus.build([TextRow("A", text, None, ("A",), regions)])
    assert corpus.entries[0].text.least == least
