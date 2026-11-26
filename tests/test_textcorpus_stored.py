# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The stored form of a corpus (``stored_rows``, ``restore``): read back, it is
the corpus ``build`` gives, whatever the rows hold; a stored form that is not
exactly the codes of the rows (other texts, other codes, another coding, rows
that are not text) gives None, so the caller builds."""
# pylint: disable=missing-function-docstring

import json
import re
from dataclasses import replace

import pytest

from licenseid import textstore
from licenseid.textcorpus import (
    TextCorpus,
    TextRow,
    critical_codes,
    critical_counts,
    critical_counts_of_codes,
    split_words,
)
from licenseid.textstore import (
    CHECK,
    CORE,
    PATTERNS,
    TEXT,
    WORDS,
    StoredRow,
    restore,
    stored_rows,
)

ROWS = (
    TextRow(
        "A-1.0", "alpha beta gamma not delta neither", "alpha beta gamma", ("A-1.0",)
    ),
    TextRow("B-1.0", "one two three four", None, ("B-1.0", "C-1.0")),
    TextRow("C-1.0", "one two three four", None, ("B-1.0", "C-1.0")),
    TextRow("D-1.0", "許諾 書 café not beta", "許諾 書", ("D-1.0",)),
    TextRow("E-1.0", "", None, ("E-1.0",)),
    TextRow("F-1.0", "alpha unless except irrevocable", "alpha", ("F-1.0",)),
)


def _stored() -> list[StoredRow]:
    return stored_rows(TextCorpus.build(ROWS))


def _replaced(kind: str, owner: str, body: str) -> list[StoredRow]:
    """The stored rows with the body of (*kind*, *owner*) changed."""
    return [
        (k, o, body) if (k, o) == (kind, owner) else (k, o, b) for k, o, b in _stored()
    ]


def _body(kind: str, owner: str) -> str:
    return next(b for k, o, b in _stored() if (k, o) == (kind, owner))


def _words_swapped() -> str:
    """The vocabulary with its first two words in the other order."""
    words = json.loads(_body(WORDS, ""))
    words[:2] = words[1::-1]
    return json.dumps(words, separators=(",", ":"))


def _swapped() -> list[StoredRow]:
    """The codes of A-1.0 and B-1.0 exchanged."""
    swap = {
        (TEXT, "A-1.0"): _body(TEXT, "B-1.0"),
        (TEXT, "B-1.0"): _body(TEXT, "A-1.0"),
    }
    return [(k, o, swap.get((k, o), b)) for k, o, b in _stored()]


def _without(kind: str, owner: str | None = None) -> list[StoredRow]:
    return [
        row
        for row in _stored()
        if not (row[0] == kind and (owner is None or row[1] == owner))
    ]


def test_the_stored_rows_read_back_as_the_corpus() -> None:
    built = TextCorpus.build(ROWS)
    restored = restore(ROWS, stored_rows(built))
    assert restored is not None
    assert restored == built
    assert [e.text.row_id for e in restored.entries] == [
        "A-1.0",
        "B-1.0",
        "D-1.0",
        "F-1.0",
    ]
    assert restored.representative("C-1.0") == "B-1.0"


def test_the_stored_rows_name_each_text_and_core_once() -> None:
    kinds = [(kind, owner) for kind, owner, _ in _stored()]
    assert kinds == [
        (WORDS, ""),
        (CHECK, ""),
        (PATTERNS, ""),
        (TEXT, "A-1.0"),
        (CORE, "A-1.0"),
        (TEXT, "B-1.0"),
        (TEXT, "D-1.0"),
        (CORE, "D-1.0"),
        (TEXT, "F-1.0"),
        (CORE, "F-1.0"),
    ]


def test_an_empty_corpus_reads_back() -> None:
    built = TextCorpus.build([])
    assert restore([], stored_rows(built)) == built


def test_the_vocabulary_is_in_code_order() -> None:
    words = json.loads(_stored()[0][2])
    assert words[:3] == ["alpha", "beta", "gamma"]
    assert list(TextCorpus.build(ROWS).vocabulary) == words


def test_critical_counts_of_codes_are_those_of_the_words() -> None:
    built = TextCorpus.build(ROWS)
    counted = critical_codes(built.vocabulary)
    for entry in built.entries:
        for coded in (entry.text, entry.core):
            if coded is not None:
                words = split_words(coded.text)
                assert coded.critical == critical_counts(words)
                assert critical_counts_of_codes(coded.codes, counted) == coded.critical


def test_a_critical_word_no_text_holds_counts_nothing() -> None:
    counted = critical_codes({"alpha": "\x01"})
    assert critical_counts_of_codes("\x01\x01", counted) == (0, 0, 0, 0)


@pytest.mark.parametrize(
    "stored",
    [
        [],
        _without(WORDS),
        _without(TEXT, "B-1.0"),
        _without(CORE, "A-1.0"),
        _without(TEXT),
        [*_stored(), (TEXT, "Z-1.0", "\x01")],  # a text no row holds
        [*_stored(), (CORE, "B-1.0", "\x01")],  # a core the row has not
        [*_stored(), (TEXT, "A-1.0", "\x01")],  # a text twice
        [*_stored(), (WORDS, "", '["x"]')],  # a vocabulary twice
        [*_stored(), ("other", "A-1.0", "\x01")],  # a kind of no meaning
        [(WORDS, "", "not json"), *_without(WORDS)],
        [(WORDS, "", '{"a": 1}'), *_without(WORDS)],
        [(WORDS, "", '["a", 1]'), *_without(WORDS)],
        [(WORDS, "", '["a", "a"]'), *_without(WORDS)],  # a word twice
        [(TEXT, "A-1.0", ""), *_without(TEXT, "A-1.0")],  # an empty text
        _without(CHECK),
        [*_stored(), (CHECK, "", "00")],  # a check twice
        _replaced(CHECK, "", ""),
        _replaced(CHECK, "", "0" * 64),
        _replaced(TEXT, "A-1.0", _body(TEXT, "A-1.0") + "\x01"),  # a code more
        _replaced(TEXT, "A-1.0", "\x02" + _body(TEXT, "A-1.0")[1:]),  # one other
        _replaced(CORE, "A-1.0", _body(TEXT, "A-1.0")),  # a text as a core
        _swapped(),
        _replaced(TEXT, "A-1.0", "".join(b for _, _, b in _stored())),  # huge
        _replaced(WORDS, "", _body(WORDS, "").replace("alpha", "ALPHA")),
        _replaced(WORDS, "", _words_swapped()),
        [(WORDS, "x", _body(WORDS, "")), *_without(WORDS)],  # an owner
        [(CHECK, "x", _body(CHECK, "")), *_without(CHECK)],
    ],
    ids=[
        "none",
        "no-vocabulary",
        "text-missing",
        "core-missing",
        "no-texts",
        "unknown-text",
        "unneeded-core",
        "text-twice",
        "vocabulary-twice",
        "unknown-kind",
        "not-json",
        "not-a-list",
        "not-strings",
        "word-twice",
        "empty-codes",
        "no-check",
        "check-twice",
        "empty-check",
        "other-check",
        "code-more",
        "code-other",
        "text-as-core",
        "swapped",
        "huge",
        "word-renamed",
        "words-swapped",
        "words-owner",
        "check-owner",
    ],
)
def test_a_stored_form_that_is_not_the_rows_codes_gives_none(
    stored: list[StoredRow],
) -> None:
    assert restore(ROWS, stored) is None


def test_the_stored_rows_of_other_rows_give_none() -> None:
    assert restore(ROWS[:1], _stored()) is None
    assert (
        restore([*ROWS, TextRow("G-1.0", "new", None, ("G-1.0",))], _stored()) is None
    )


def _rows_with(license_id: str, text: str) -> list[TextRow]:
    """ROWS with the text of *license_id* changed."""
    return [
        replace(row, text=text) if row.license_id == license_id else row for row in ROWS
    ]


@pytest.mark.parametrize(
    "rows",
    [
        _rows_with("A-1.0", "alpha beta gamma not delta neither one more"),
        _rows_with("A-1.0", "alpha beta gamma not delta"),
        _rows_with("B-1.0", "four three two one"),  # same words, other order
        [
            replace(row, core="alpha beta") if row.core == "alpha" else row
            for row in ROWS
        ],
        [replace(row, core=None) if row.license_id == "D-1.0" else row for row in ROWS],
    ],
    ids=["stale-text", "text-cut", "words-reordered", "stale-core", "core-gone"],
)
def test_the_codes_of_other_texts_give_none(rows: list[TextRow]) -> None:
    """The case of an older program that rewrote the rows and left the codes:
    the names, the vocabulary and the shape of the rows may all agree."""
    assert restore(rows, _stored()) is None


def test_a_text_and_core_cut_at_another_place_give_none() -> None:
    """The same characters in the text and the core together, cut elsewhere."""
    built = [TextRow("A-1.0", "aa bb", "cc", ("A-1.0",))]
    cut = [TextRow("A-1.0", "aa bbc", "c", ("A-1.0",))]
    stored = stored_rows(TextCorpus.build(built))
    assert restore(built, stored) is not None
    assert restore(cut, stored) is None


def test_a_coding_of_another_version_gives_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _stored()
    assert restore(ROWS, stored) is not None
    monkeypatch.setattr(textstore, "CODING_VERSION", textstore.CODING_VERSION + 1)
    assert restore(ROWS, stored) is None
    assert restore(ROWS, stored_rows(TextCorpus.build(ROWS))) is not None


def test_a_token_pattern_of_another_coding_gives_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _stored()
    monkeypatch.setattr(textstore, "TOKEN", re.compile(r"\S+"))
    assert restore(ROWS, stored) is None


def test_the_check_is_of_the_coding_not_of_the_run() -> None:
    assert _body(CHECK, "") == _body(CHECK, "")
    other = stored_rows(TextCorpus.build(ROWS[:1]))
    assert [b for k, _, b in other if k == CHECK] != [_body(CHECK, "")]


@pytest.mark.parametrize(
    "stored",
    [
        [(WORDS, "", b'["a"]'), *_without(WORDS)],  # bytes json.loads accepts
        [(TEXT, "A-1.0", b"AB"), *_without(TEXT, "A-1.0")],
        [(CORE, "A-1.0", b"AB"), *_without(CORE, "A-1.0")],
        [(CHECK, "", b"00"), *_without(CHECK)],
        [(b"text", "A-1.0", "\x01"), *_without(TEXT, "A-1.0")],
        [(TEXT, b"A-1.0", "\x01"), *_without(TEXT, "A-1.0")],
        [(TEXT, "A-1.0", None), *_without(TEXT, "A-1.0")],
        [(TEXT, "A-1.0", 5), *_without(TEXT, "A-1.0")],
        [(TEXT, 5, "\x01"), *_without(TEXT, "A-1.0")],
        [(None, "A-1.0", "\x01"), *_without(TEXT, "A-1.0")],
    ],
    ids=[
        "words-bytes",
        "text-bytes",
        "core-bytes",
        "check-bytes",
        "kind-bytes",
        "owner-bytes",
        "body-none",
        "body-int",
        "owner-int",
        "kind-none",
    ],
)
def test_a_row_that_is_not_text_gives_none_not_an_error(
    stored: list[tuple[object, ...]],
) -> None:
    """A BLOB column value comes back as bytes: no code to count."""
    assert restore(ROWS, stored) is None  # type: ignore[arg-type]
