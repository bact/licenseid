# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The List texts the whole-text search of one input reads: one set per
input, and the searches made on it.

The search of ``TEXTS`` (``licenseid.wholetexts.found_texts``) reads the
texts of a candidate set, not of the whole List (plan of 0.10.0, section 3.1,
step 5): the texts that share the most word 3-grams with the input and every
text it holds half of (``licenseid.gramselect.searched``). The set is made
once per input from its gram score table, unfiltered (``exclude``,
``only_spdx`` and ``only_common`` never touch ``TEXTS``), and every caller of
the search reads it: the narrowing of Tier 2 (``licenseid.retrieval``),
``licenseid.markerfloor``, ``licenseid.firsttext``, ``licenseid.textnames``
and ``LicenseDetector.texts``. Each search is made once per answer it ranks
first: a second caller with the same answer reads the first one's result.

Past the bound on grams looked up (``gramselect.GRAM_LIMIT``) there is no
search: ``TEXTS`` is None, never a partial list.

One object per ``detect()`` or ``texts()`` call, never shared between calls
or threads: it keeps the results of its searches. The corpus it cuts from is
immutable (``licenseid.textcorpus``).
"""

from collections.abc import Callable

from licenseid.gramselect import searched
from licenseid.textcorpus import TextCorpus
from licenseid.textgrams import GramTable
from licenseid.textnames import has_tokens
from licenseid.wholetexts import Found, found_texts

__all__ = ["TextCandidates", "cut"]


def cut(corpus: TextCorpus, ids: list[str]) -> TextCorpus:
    """The corpus of the same-text groups of the licences *ids*, its entries
    in *corpus*'s order (a tie of the search keeps the order the whole
    corpus gives), with *corpus*'s vocabulary and names."""
    names = {corpus.representative(license_id) for license_id in ids}
    return TextCorpus(
        vocabulary=corpus.vocabulary,
        entries=tuple(e for e in corpus.entries if e.text.row_id in names),
        representatives=corpus.representatives,
    )


def _core_grams(corpus: TextCorpus) -> Callable[[str], int | None]:
    """The distinct grams of the core of a licence's text in *corpus*, None
    when it has no core."""

    def grams(license_id: str) -> int | None:
        entry = corpus.entry(license_id)
        return None if entry is None or entry.core is None else entry.core.gram_count

    return grams


class TextCandidates:
    """The texts the whole-text search of the normalised input *norm_input*
    reads, from its gram score table (*lookup*, made at the first use), cut
    from the List's corpus (*corpus*, read at the first search)."""

    def __init__(
        self,
        norm_input: str,
        lookup: Callable[[], GramTable],
        corpus: Callable[[], TextCorpus],
    ) -> None:
        self.norm_input = norm_input
        self._lookup = lookup
        self._corpus = corpus
        self._table: GramTable | None = None
        self._cut: TextCorpus | None = None
        self._found: dict[str | None, Found | None] = {}

    @property
    def table(self) -> GramTable:
        """The texts that share a gram with the input (unfiltered)."""
        if self._table is None:
            self._table = self._lookup()
        return self._table

    def corpus(self) -> TextCorpus:
        """The texts of the set as a corpus, cut once."""
        if self._cut is None:
            whole = self._corpus()
            ids = searched(self.table.rows, _core_grams(whole))
            self._cut = cut(whole, ids)
        return self._cut

    def found(self, answer_id: str) -> Found | None:
        """The whole texts the input holds among the set's
        (``wholetexts.found_texts``, *answer_id*'s group first of equals; ""
        for none), searched once per answer group. None when the input is
        too short to hold a text, or past the bound on grams looked up."""
        if not has_tokens(self.norm_input) or self.table.bounded:
            return None
        corpus = self.corpus()
        if not corpus.entries:  # no text shares a gram: none is held whole
            return None
        key = corpus.representative(answer_id)
        if key not in self._found and self._unranked_holds(key):
            return self._found[None]
        if key not in self._found:
            self._found[key] = found_texts(self.norm_input, corpus, answer_id)
        return self._found[key]

    def _unranked_holds(self, key: str | None) -> bool:
        """Whether the search made with no answer stands for the search with
        the answer group *key*: it found nothing, or that group's text alone.
        An answer only breaks ties of equal fits in its favour, so it cannot
        add a text there; a measured shortcut (no search of the 868 core
        inputs, the 183 many-text, the CJK, roadmap, prose and option inputs
        differs), which spares the second search of nearly every input."""
        if None not in self._found:
            return False
        found = self._found[None]
        return found is None or found.rows == [key]
