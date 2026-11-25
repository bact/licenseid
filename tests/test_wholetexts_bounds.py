# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Bounds and guards of the ``TEXTS`` search: which texts are long enough
to fit the input, when a core is tried, the trimming of an alignment, and
the token gate.

The texts are made up. ``HELD`` is 60 numbered words of 4 characters (299
characters); a longer text is ``HELD`` with one more word of *k* letters,
which a copy of ``HELD`` lacks: it fits that copy at ``1 - (k + 1) / (599 +
k)``."""
# pylint: disable=missing-function-docstring

import pytest
from test_wholetexts import FILLER, corpus_of, fake

from licenseid import textnames, wholetexts
from licenseid.textlocate import Alignment, align, can_reach, sample_share
from licenseid.wholetexts import found_rows

HELD_WORDS = [f"q{i:03d}" for i in range(60)]
HELD = " ".join(HELD_WORDS)


def _longer(letters: int) -> str:
    """``HELD`` with a word of *letters* letters in its middle."""
    return " ".join([*HELD_WORDS[:30], "x" * letters, *HELD_WORDS[30:]])


def _changed(count: int) -> str:
    """``HELD`` with *count* words inside it changed, 10 words apart: it
    fits ``HELD`` at 0.973 (2) or 0.960 (3)."""
    return " ".join(
        "zzzz" if i in range(10, 10 * count + 1, 10) else word
        for i, word in enumerate(HELD_WORDS)
    )


@pytest.mark.parametrize(
    ("length", "size", "similarity", "expected"),
    [
        (1105, 1000, 0.95, True),
        (1106, 1000, 0.95, False),
        (1150, 1000, 0.93, True),
        (1151, 1000, 0.93, False),
        (21, 19, 0.95, True),
        (900, 1000, 0.95, True),
    ],
    ids=["hit-1105", "hit-1106", "near-1150", "near-1151", "equal", "shorter"],
)
def test_can_reach(length: int, size: int, similarity: float, expected: bool) -> None:
    # 2 x size / (length + size): 2000 / 2105 = 0.9501, 2000 / 2106 = 0.9497;
    # 2000 / 2150 = 0.9302; 38 / 40 = 0.95 exactly.
    assert can_reach(length, size, similarity) is expected


def test_a_damaged_copy_is_not_named_by_a_part_of_it() -> None:
    # The input lost T's 21-character word (T fits at 0.966, key 278); Part,
    # its first 45 words, fits whole (key 224): too short to doubt T.
    corpus = corpus_of({"T": _longer(20), "Part": " ".join(HELD_WORDS[:45])})
    assert found_rows(HELD, corpus, "Z") == ["T"]


def test_a_damaged_copy_is_not_named_by_a_shorter_neighbour() -> None:
    # Short fits at 0.973 (key 283), T at 0.966 (key 278): about as close,
    # so neither is named.
    corpus = corpus_of({"T": _longer(20), "Short": _changed(2)})
    assert found_rows(HELD, corpus, "Z") is None
    assert found_rows(HELD, corpus_of({"Short": _changed(2)}), "Z") == ["Short"]


def test_a_text_only_a_look_alike_fit_reaches_casts_doubt() -> None:
    # T (340 characters, 1.137 times the input) fits at 1 - 41 / 639 =
    # 0.936, key 258: no hit, but a look-alike of Short (key 283).
    corpus = corpus_of({"T": _longer(40), "Short": _changed(2)})
    assert found_rows(HELD, corpus, "Z") is None


def test_a_text_too_long_to_be_a_hit_is_not_aligned_as_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def counted(text: str, window: str) -> Alignment | None:
        calls.append(text)
        return align(text, window)

    monkeypatch.setattr(wholetexts, "align", counted)
    assert found_rows(HELD, corpus_of({"T": _longer(40)}), "T") is None
    assert not calls


def test_a_core_is_tried_when_the_text_holds_a_fifth_of_the_samples() -> None:
    # The core is a fifth of the text: of the text's samples the input holds
    # about a fifth, under MIN_VOTE_SHARE (0.30) but over half the core's
    # share of it (0.03).
    core = fake(20, 40)
    text = f"{core} {fake(21, 160)}"
    corpus = corpus_of({"P": text}, cores={"P": core})
    assert found_rows(f"{FILLER} {core}", corpus, "P") == ["P"]


def test_a_core_is_not_sampled_when_the_text_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def counted(codes: str, index: dict[str, list[int]]) -> float:
        calls.append(codes)
        return sample_share(codes, index)

    monkeypatch.setattr(wholetexts, "sample_share", counted)
    core = fake(20, 40)
    corpus = corpus_of({"P": f"{core} {fake(21, 160)}"}, cores={"P": core})
    assert found_rows(f"{FILLER} {fake(22, 40)}", corpus, "P") is None
    assert len(calls) == 1


def test_align_drops_two_stray_blocks_where_one_alone_lowers_the_ratio() -> None:
    # Blocks of 1, 1 and 58 words: dropping the first alone gives 118 / 139
    # (under 120 / 141), dropping both 116 / 118.
    text = "".join(chr(0x4E00 + i) for i in range(60))
    filler = "".join(chr(0x3041 + i) for i in range(21))
    window = text[0] + filler[0] + text[1] + filler[1:] + text[2:]
    assert align(text, window) == Alignment(23, 81, ((0, 2),), (2, 0))


_SPLITS: list[int] = []


class _CountedSplit(str):
    """A string that keeps the length of each split it gives in _SPLITS."""

    __slots__ = ()

    def split(  # type: ignore[override]
        self, sep: str | None = None, maxsplit: int = -1
    ) -> list[str]:
        parts = super().split(sep, maxsplit)
        _SPLITS.append(len(parts))
        return parts


def test_the_token_gate_splits_no_more_than_it_needs() -> None:
    _SPLITS.clear()
    assert textnames.has_tokens(_CountedSplit(" ".join(["word"] * 10_000)))
    assert _SPLITS == [41]
