# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``wholetexts.found_rows``: which List texts an input holds whole.

Every licence here is made up: 40 to 80 words of nonsense syllables, so no
two texts share a 5-gram unless a test makes them."""
# pylint: disable=missing-function-docstring

import random
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from timing import slack

from licenseid import textlocate, wholetexts
from licenseid.textcorpus import TextCorpus, TextRow
from licenseid.textlocate import Alignment, align
from licenseid.wholetexts import found_rows

_SYLLABLES = ("ka", "lo", "mi", "ra", "tu", "ne", "po", "si", "va", "de", "fo", "gu")


def fake(seed: int, words: int = 60) -> str:
    """A made-up text of *words* words."""
    rng = random.Random(seed)
    return " ".join(
        "".join(rng.choice(_SYLLABLES) for _ in range(rng.randint(2, 4)))
        for _ in range(words)
    )


def corpus_of(texts: dict[str, str], cores: dict[str, str] | None = None) -> TextCorpus:
    """A corpus of *texts* by ID, each its own group."""
    cores = cores or {}
    return TextCorpus.build(
        TextRow(key, text, cores.get(key), (key,)) for key, text in texts.items()
    )


A, B, C = fake(1), fake(2, 70), fake(3, 50)
NOTICE = fake(90, 30)
FILLER = fake(91, 30)
CORPUS = corpus_of({"A": A, "B": B, "C": C})


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (A, ["A"]),
        (f"{A} {B}", ["A", "B"]),
        (f"{B} {FILLER} {A} {NOTICE} {C}", ["A", "B", "C"]),
        (f"{NOTICE} {B}", ["B"]),
        (f"{A} {A} {A}", ["A"]),
        (f"{NOTICE} {FILLER}", None),
    ],
    ids=["whole", "two", "three", "notice-and-text", "copies", "notice"],
)
def test_found(text: str, expected: list[str] | None) -> None:
    assert found_rows(text, CORPUS, "A") == expected


def test_a_copy_between_two_others_is_found() -> None:
    # The padded window holds 12 words of the fillers: only the trimmed
    # span scores 1.
    assert found_rows(f"{NOTICE} {A} {FILLER}", CORPUS, "B") == ["A"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [(f"{A} {fake(4, 3)}", ["Long"]), (f"{FILLER} {A}", ["A"])],
    ids=["longer-held", "shorter-held"],
)
def test_nested_texts(text: str, expected: list[str]) -> None:
    corpus = corpus_of({"A": A, "Long": f"{A} {fake(4, 3)}"})
    assert found_rows(text, corpus, "Z") == expected
    assert found_rows(text, corpus, "A") == expected
    assert found_rows(text, corpus, "Long") == expected


def test_a_longer_look_alike_loses_to_the_exact_text() -> None:
    longer = A.replace(A.split()[30], "kalomira kalomira", 1)
    corpus = corpus_of({"A": A, "Look": longer})
    assert found_rows(f"{FILLER} {A}", corpus, "Look") == ["A"]


def _numbered(count: int) -> list[str]:
    return [f"q{i:03d}" for i in range(count)]


@pytest.mark.parametrize(("words", "expected"), [(39, None), (40, ["T"])])
def test_text_floor(words: int, expected: list[str] | None) -> None:
    text = " ".join(_numbered(words))
    assert found_rows(f"{text} {FILLER}", corpus_of({"T": text}), "T") == expected


@pytest.mark.parametrize(("words", "expected"), [(39, None), (40, ["T"])])
def test_input_floor(words: int, expected: list[str] | None) -> None:
    held = _numbered(words)
    text = " ".join(held[:20] + ["ab"] + held[20:])
    assert found_rows(" ".join(held), corpus_of({"T": text}), "T") == expected


@pytest.mark.parametrize(("last", "expected"), [(20, ["T"]), (21, None)])
def test_text_longer_than_the_input(last: int, expected: list[str] | None) -> None:
    # 221 characters in 200 fit at 1 - 21 / 421 = 0.9501, 222 at 0.9479: a
    # text that lost a clause is tried while its fit can reach the floor.
    held = _numbered(40)
    held[0] = "q0000"
    source = " ".join(held)
    text = f"{source} {'w' * last}"
    assert (len(source), len(text)) == (200, 201 + last)
    assert found_rows(source, corpus_of({"T": text}), "T") == expected


@pytest.mark.parametrize(("changed", "expected"), [(20, ["T"]), (21, None)])
def test_similarity_threshold(changed: int, expected: list[str] | None) -> None:
    # 400 characters; each "#" costs 2 of the 800: 95 % is 20 of them.
    held = _numbered(60)
    text = " ".join([*held[:30], "v" * 100, *held[30:]])
    assert len(text) == 400
    source = text.replace("v" * changed, "#" * changed, 1)
    assert found_rows(source, corpus_of({"T": text}), "T") == expected


def test_a_typo_every_eight_words_is_found() -> None:
    words = A.split()
    typos = [w + "s" if i % 8 == 7 else w for i, w in enumerate(words)]
    assert found_rows(f"{FILLER} {' '.join(typos)}", CORPUS, "A") == ["A"]


def test_a_window_a_kept_span_half_covers_is_not_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    words = A.split()
    shorter = " ".join(words[:30] + ["ka"] + words[31:])
    assert len(shorter) < len(A)
    calls: list[str] = []

    def counted(text: str, window: str) -> Alignment | None:
        calls.append(text)
        return align(text, window)

    monkeypatch.setattr(wholetexts, "align", counted)
    corpus = corpus_of({"A": A, "Look": shorter})
    assert found_rows(f"{FILLER} {A}", corpus, "Look") == ["A"]
    assert len(calls) == 1


def test_a_dropped_critical_word_is_not_the_text() -> None:
    words = A.split()
    text = " ".join(words[:30] + ["not"] + words[30:])
    corpus = corpus_of({"N": text})
    assert found_rows(f"{FILLER} {text}", corpus, "N") == ["N"]
    assert found_rows(f"{FILLER} {A}", corpus, "N") is None


def _tied() -> tuple[str, str, str]:
    """Two texts and an input that fit both alike: one word each differs
    from the input's, by letters found nowhere else."""
    words = _numbered(60)
    return tuple(  # type: ignore[return-value]
        " ".join(words[:30] + [odd * 4] + words[30:]) for odd in "kmt"
    )


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("Second", ["Second"]), ("First", ["First"]), ("Z", ["First"])],
)
def test_a_tie_goes_to_the_answer_then_the_id(answer: str, expected: list[str]) -> None:
    first, second, source = _tied()
    corpus = corpus_of({"First": first, "Second": second})
    assert found_rows(source, corpus, answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"), [("Short", ["Short"]), ("Long", ["Long"]), ("Z", ["Long"])]
)
def test_a_tie_waits_for_the_shorter_text(answer: str, expected: list[str]) -> None:
    # "Long" (bound 2 more) is scored first, at the key "Short" reaches
    # only once scored: the tie must still go to the answer.
    held = _numbered(60)
    short = " ".join(held)
    long = " ".join([*held[:30], "x", *held[30:]])
    source = " ".join([*held[:30], "y", *held[30:]])
    corpus = corpus_of({"Short": short, "Long": long})
    assert found_rows(source, corpus, answer) == expected


def test_twins_are_named_by_their_representative() -> None:
    group = ("Z-only", "Z-or-later")
    corpus = TextCorpus.build(TextRow(key, A, None, group) for key in group)
    assert len(corpus.entries) == 1
    assert found_rows(A, corpus, "Z-or-later") == ["Z-only"]
    assert found_rows(A, corpus, "Other") == ["Z-only"]


def test_a_core_is_found_without_the_optional_parts() -> None:
    corpus = corpus_of({"P": f"{A} {fake(5, 40)}"}, cores={"P": A})
    assert found_rows(f"{FILLER} {A}", corpus, "P") == ["P"]
    assert (
        found_rows(f"{FILLER} {A}", corpus_of({"P": f"{A} {fake(5, 40)}"}), "P") is None
    )


@pytest.mark.parametrize(
    ("shared", "expected"),
    [(6, ["Head", "Tail"]), (7, ["Head"]), (20, ["Head"])],
)
def test_overlap_of_a_tenth(shared: int, expected: list[str]) -> None:
    head = fake(6)
    tail_words = head.split()[-shared:] + fake(7, 60 - shared).split()
    tail = " ".join(tail_words)
    assert len(head) > len(tail)
    source = f"{head} {' '.join(tail_words[shared:])}"
    corpus = corpus_of({"Head": head, "Tail": tail})
    assert found_rows(source, corpus, "Z") == expected


def test_every_copy_is_claimed_before_names_are_deduped() -> None:
    base = fake(8, 50)
    words = base.split()
    look_alike = " ".join(words[:25] + ["pomira"] + words[26:])
    json_like = f"{base} vasi gu"
    corpus = corpus_of({"MIT": base, "Look": look_alike, "JSON": json_like})
    source = " ".join([base] * 100 + [json_like])
    assert found_rows(source, corpus, "MIT") == ["JSON", "MIT"]


def _holder(name: str) -> str:
    """60 numbered words with a holder's *name* among them: one made-up
    licence and its look-alikes differ only there."""
    held = _numbered(60)
    return " ".join([*held[:50], name, *held[50:]])


# The List's own wording, a look-alike's ("the author"), and the name a
# project filled in, which fits the two at 0.958 and 0.968 (keys 294, 300).
HOLDERS, AUTHOR, FILLED = _holder("k" * 6), _holder("tttmmm"), _holder("t" * 20)


@pytest.mark.parametrize(
    ("texts", "expected"),
    [
        ({"P": HOLDERS, "Q": AUTHOR}, None),
        ({"P": HOLDERS}, ["P"]),
        ({"Q": AUTHOR}, ["Q"]),
    ],
    ids=["look-alikes", "first-alone", "second-alone"],
)
def test_look_alikes_that_fit_alike_name_neither(
    texts: dict[str, str], expected: list[str] | None
) -> None:
    assert found_rows(f"{NOTICE} {FILLED}", corpus_of(texts), "P") == expected


@pytest.mark.parametrize(("holder", "expected"), [(6, None), (19, None), (20, ["Q"])])
def test_a_near_miss_under_the_gate_casts_doubt(
    holder: int, expected: list[str] | None
) -> None:
    # Q fits at 0.966; P at 0.949 and 0.930 (look-alikes), 0.929 (not).
    corpus = corpus_of({"P": _holder("k" * holder), "Q": _holder("t" * 10 + "m" * 6)})
    assert found_rows(_holder("t" * 26), corpus, "Q") == expected


@pytest.mark.parametrize(("added", "expected"), [(0, ["P"]), (12, ["P"]), (13, None)])
def test_a_hit_from_0_98_is_not_doubted(added: int, expected: list[str] | None) -> None:
    # P fits at 1, 0.981 and 0.979; the look-alike at 0.98 or 0.97.
    corpus = corpus_of({"P": HOLDERS, "Q": AUTHOR})
    assert found_rows(_holder("k" * 6 + "t" * added), corpus, "Z") == expected


@pytest.mark.parametrize(("cut", "expected"), [(4, None), (5, ["Q"])])
def test_a_look_alike_keys_at_nine_tenths_of_the_hit(
    cut: int, expected: list[str] | None
) -> None:
    # Q keys 304; P less its last words 274 (0.901 of it) or 269 (0.885).
    held = _holder("k" * 6).split()
    corpus = corpus_of({"P": " ".join(held[:-cut]), "Q": _holder("t" * 10 + "m" * 6)})
    assert found_rows(_holder("t" * 26), corpus, "Q") == expected


def test_a_text_the_hit_holds_as_a_part_is_no_look_alike() -> None:
    part = " ".join(_numbered(45))  # key 224 of P's 294
    assert found_rows(FILLED, corpus_of({"P": HOLDERS, "Part": part}), "Z") == ["P"]


def test_a_text_too_short_to_be_a_look_alike_is_not_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A key is at most its text's length: 224 cannot reach 0.9 of 294.
    calls: list[str] = []

    def counted(text: str, window: str) -> Alignment | None:
        calls.append(text)
        return align(text, window)

    monkeypatch.setattr(wholetexts, "align", counted)
    part = " ".join(_numbered(45))
    assert found_rows(FILLED, corpus_of({"P": HOLDERS, "Part": part}), "Z") == ["P"]
    assert len(calls) == 1


def test_a_doubted_span_lets_no_third_text_in() -> None:
    # The part fits at 1, but it is the span the look-alikes share.
    part = " ".join(_numbered(45))
    corpus = corpus_of({"P": HOLDERS, "Q": AUTHOR, "Part": part})
    assert found_rows(FILLED, corpus, "Z") is None


def test_a_look_alike_elsewhere_in_the_input_casts_no_doubt() -> None:
    other = fake(12)
    corpus = corpus_of({"P": HOLDERS, "Other": other})
    assert found_rows(f"{FILLED} {other}", corpus, "Z") == ["Other", "P"]


def test_a_look_alike_that_says_not_is_no_rival() -> None:
    # As JSON is MIT with "not evil": the input has no "not".
    corpus = corpus_of({"P": HOLDERS, "Not": _holder("not kkkkkk")})
    assert found_rows(FILLED, corpus, "Z") == ["P"]


@pytest.mark.parametrize(
    ("other", "fits"), [("kkkk", 0.992), ("k" * 24, 0.960)], ids=["sure", "near"]
)
def test_a_text_refused_by_a_critical_word_still_casts_doubt(
    other: str, fits: float
) -> None:
    # The input holds "Not" less its "not" (key 295): "Not" is refused, and
    # the look-alike that keeps the counts, at 0.992 or 0.960 (keys 294,
    # 274), must not be named. Alone, it is.
    held, look = " ".join(_numbered(60)), _holder(other)
    assert round(1 - (len(look) - len(held)) / (len(look) + len(held)), 3) == fits
    source = f"{FILLER} {held}"
    corpus = corpus_of({"Not": _holder("not"), "Look": look})
    assert found_rows(source, corpus, "Look") is None
    assert found_rows(source, corpus_of({"Look": look}), "Look") == ["Look"]


def test_a_look_alike_that_says_not_keys_too_low_to_doubt_a_sure_hit() -> None:
    # The input is P; "Not" is P with a "not" (key 295 of P's 299).
    corpus = corpus_of({"P": _holder("kkkk"), "Not": _holder("not kkkk")})
    assert found_rows(_holder("kkkk"), corpus, "Z") == ["P"]


@pytest.mark.parametrize(("changed", "expected"), [(4, None), (5, ["P"]), (6, ["P"])])
def test_a_text_refused_by_a_critical_word_doubts_only_as_a_hit(
    changed: int, expected: list[str] | None
) -> None:
    # The input is P and 20 words more; "Not" is P, "not" and those words
    # with *changed* of them altered: keys 363, 355, 347 above P's 299, at
    # 0.955 (a hit but for its "not"), 0.945 and 0.935 (no hit: no doubt).
    held, extra = " ".join(_numbered(60)), [f"r{i:03d}" for i in range(20)]
    altered = [
        "xxxx" if i < 2 * changed and i % 2 == 0 else w for i, w in enumerate(extra)
    ]
    corpus = corpus_of({"P": held, "Not": f"{held} not {' '.join(altered)}"})
    assert found_rows(f"{FILLER} {held} {' '.join(extra)}", corpus, "Z") == expected


def test_a_text_and_its_core_cast_no_doubt_on_each_other() -> None:
    # The text with its optional "zz" fits at 0.953, the core at 0.958.
    corpus = corpus_of({"P": f"{HOLDERS} zz"}, cores={"P": HOLDERS})
    assert found_rows(FILLED, corpus, "Z") == ["P"]


def test_twins_cast_no_doubt_on_each_other() -> None:
    group = ("Z-only", "Z-or-later")
    corpus = TextCorpus.build(TextRow(key, HOLDERS, None, group) for key in group)
    assert found_rows(FILLED, corpus, "Z-or-later") == ["Z-only"]


def _clause(clause: str) -> str:
    """A made-up BSD-like text of 50 words with *clause* in its middle."""
    held = fake(11, 50).split()
    return " ".join([*held[:25], clause, *held[25:]])


@pytest.mark.parametrize(
    ("clause", "expected"),
    [("the names may not be used", ["T"]), ("the names may be used", None)],
    ids=["reworded", "negation-dropped"],
)
def test_may_not_be_used_reads_as_neither_nor(
    clause: str, expected: list[str] | None
) -> None:
    text = _clause("neither the name nor the names may be used")
    source = f"{FILLER} {_clause(clause)}"
    assert found_rows(source, corpus_of({"T": text}), "T") == expected


def test_cjk_text_is_found_by_characters() -> None:
    rng = random.Random(9)
    text = "".join(chr(0x4E00 + rng.randrange(2000)) for _ in range(80))
    changed = text[:40] + "了" + text[41:]
    corpus = corpus_of({"JP": text})
    assert found_rows(f"{FILLER} {changed} {NOTICE}", corpus, "JP") == ["JP"]


def test_a_cjk_blob_is_refused_fast() -> None:
    rng = random.Random(10)
    blob = "".join(chr(0x3041 + rng.randrange(80)) for _ in range(300_000))
    started = time.monotonic()
    assert found_rows(blob, CORPUS, "A") is None
    assert time.monotonic() - started < slack(0.5)


def _two_texts_limit(
    monkeypatch: pytest.MonkeyPatch, limit: str, value: int
) -> list[str] | None:
    monkeypatch.setattr(textlocate, limit, value)
    return found_rows(f"{A} {B}", CORPUS, "A")


@pytest.mark.parametrize(
    ("limit", "passes", "fails"),
    [
        ("MAX_INPUT_CHARS", len(f"{A} {B}"), len(f"{A} {B}") - 1),
        ("MAX_INPUT_TOKENS", 130, 129),
        ("MAX_VOTES", 1_000, 1),
        ("MAX_WINDOWS", 2, 1),
        ("MAX_WORD_CELLS", 10**6, 70 * 80),
        ("MAX_CHAR_CELLS", len(A) * len(A) + len(B) * len(B), len(B) * len(B)),
    ],
)
def test_past_a_limit_nothing_is_found(
    monkeypatch: pytest.MonkeyPatch, limit: str, passes: int, fails: int
) -> None:
    # B is scored first (the longer), so a limit that A's charge passes
    # finds B alone before it: the answer must still be nothing.
    assert len(B) > len(A)
    assert _two_texts_limit(monkeypatch, limit, passes) == ["A", "B"]
    assert _two_texts_limit(monkeypatch, limit, fails) is None


def test_floors_are_the_documented_ones() -> None:
    assert (wholetexts.MIN_WORDS, wholetexts.MIN_INPUT_WORDS) == (40, 40)
    assert (textlocate.MIN_SIMILARITY, textlocate.WORD_GATE) == (0.95, 0.80)


def test_threads_share_one_corpus() -> None:
    inputs = [f"{A} {B}", f"{NOTICE} {C}", A, f"{NOTICE} {FILLER}"] * 8
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda text: found_rows(text, CORPUS, "A"), inputs))
    assert results == [found_rows(text, CORPUS, "A") for text in inputs]
