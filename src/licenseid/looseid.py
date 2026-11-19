# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A license ID written loosely: "Apache2", "GPLv3", "Apache_2.0",
"CC by 3 nl", "GPLv2 or any later version".

A short input and every ID get one version key (version_key); the input names
the one ID with its key. Tier 0 (licenseid.shorttext) asks this before its
exact and fuzzy matches.

Also the judges of a declared value's reading: where its "or later" grant
starts and ends (:func:`granted_id_text`, :func:`declared_grant_id_text`,
:func:`grant_stop`), what a reading must not drop (:func:`drops_words`,
:func:`lists_after_grant`, :func:`lists_another`) and which deprecated IDs it
decided (:func:`decided_forms`, :func:`read_inexactly`).
"""

import re

from licenseid.classify import OR_LATER_PHRASE, grant_end, grant_follows, grant_head
from licenseid.deprecatedids import DEPRECATED_WITH_IDS
from licenseid.dropguard import glued_marks, glued_tag_marks, trim_end_mark
from licenseid.exprtokens import (
    ID_WORD,
    LIST_MARK,
    RE_OPERATOR,
    RE_TOKEN,
    WHITE_SPACE,
    is_license_ref,
    token_kind,
)
from licenseid.identifiers import (
    bare_deprecated,
    disambiguate_deprecated_id,
    names_only_listed,
    normalize_identifier,
    qualify_trailing_grant,
    without_outer_brackets,
)
from licenseid.listlookup import ListedName, ListLookup
from licenseid.normalize import DASHES
from licenseid.plusoperator import PLUS_OPERATOR
from licenseid.types import CandidateMatch, Evidence, RawMatch
from licenseid.variants import ONLY_WORD, decided, family_of, warn_guess
from licenseid.versionkey import (
    MAX_KEY_INPUT,
    ambiguous_ids,
    keyed_row,
    named_row,
    version_key,
)

# grant_end is classify's, the one probe of a grant after an ID; the
# compound reader (exprcanon) imports it from here.
__all__ = [
    "RE_GRANT_WORDS",
    "WITH_OPERATOR",
    "before_grant",
    "declared_grant_id_text",
    "drops_words",
    "grant_end",
    "grant_stop",
    "granted_id_text",
    "lists_another",
    "loose_id",
    "loose_with",
    "mark_guessed",
    "operator_at",
    "resolved_id",
    "restates_qualifier",
    "undashed_grant",
]

# The word a grant starts with, where OR_LATER_PHRASE starts at the version
# before it ("2 or later").
_RE_GRANT_WORD = re.compile(r"\bor\b", re.IGNORECASE)
# The words that may follow a grant: "version", "of the License". A word
# ignores case in ASCII only ("(?a:"), as every keyword here does: Python's
# IGNORECASE alone folds "\u0130", "\u0131", "\u017f" and the Kelvin sign
# into "i", "s" and "k"; the white space between them stays Unicode's.
_GRANT_WORDS = r"(?:\s+(?a:versions?))?(?:\s+of\s+(?a:the|this)\s+(?a:licen[cs]e))?"
# The gaps around the "or" of a grant after the ID: where a dash between
# words may stand (classify.grant_head, OR_LATER_PHRASE).
_RE_GRANT_GAPS = re.compile(
    f"([\\s,(\\[{DASHES}]*)((?a:or))([\\s{DASHES}]*)", re.IGNORECASE
)
_NO_DASHES = str.maketrans("", "", DASHES)
_RE_WHITE_RUN = re.compile(r"\s+")
# A listing mark and the word after it, which may be another licence.
_RE_LISTED = re.compile(f"{LIST_MARK}({ID_WORD})")
#: The words that may end a grant, as a pattern to match where it ends.
RE_GRANT_WORDS = re.compile(_GRANT_WORDS, re.IGNORECASE)
# What may follow the grant at the end of the text: those words, then
# punctuation, the bracket that closes "(or later)" or "[or later]".
_RE_GRANT_TAIL = re.compile(_GRANT_WORDS + r"[\s.,;:)\]]*", re.IGNORECASE)
# The WITH of a simple expression ("GPL2 WITH Classpath-exception-2.0"). The
# match starts at the first white space of a run (lookbehind): without it,
# every offset of a long run of spaces is tried and a split is quadratic
# (1.6 s at 20,000 spaces).
WITH_OPERATOR = re.compile(r"(?<!\s)\s+(?a:WITH)\s+", re.IGNORECASE)


def loose_id(
    db: ListLookup, text: str, *, granted: bool = False
) -> tuple[ListedName, str] | None:
    """The row *text* names loosely, and the ID it answers: the row's own,
    its successor if deprecated, or its -or-later form for a grant after it
    ("GPLv2 or any later version"). None for no row, for two rows in use, or
    for a cut ID that names no one of several: ``Apache-1`` writes only the
    major, and the List has ``Apache-1.0`` and ``Apache-1.1``
    (:func:`licenseid.versionkey.ambiguous_ids`). *granted*: the caller has
    read a grant off the text (``LGPLv2+``), which covers every later minor,
    so the lowest is what was written and nothing is ambiguous."""
    text = text.strip()
    if len(text) > MAX_KEY_INPUT:
        return None
    row = named_row(db, text)
    if row is not None:
        if not granted and ambiguous_ids(db, text):
            return None
        return row, resolved_id(db, row)
    return _granted(db, text)


def resolved_id(db: ListLookup, row: ListedName) -> str:
    """The ID a hit on *row* answers. A deprecated ID goes through
    normalize_identifier() for the same canonical-successor redirect the
    license_id= path gets; it can resolve to an expression."""
    lid = row["license_id"]
    return normalize_identifier(lid, db) if row["is_deprecated"] else lid


def decided_forms(db: ListLookup, text: str, expression: str) -> list[str]:
    """The forms (folded) that *expression*, the reading of the declared
    *text*, decided a deprecated ID of *text* as, not stated ("MIT OR
    GPL-2.0" read as "GPL-2.0-only OR MIT", "GPL-2.0-with-classpath-exception"
    as "GPL-2.0-only WITH Classpath-exception-2.0"). Each ID word is read
    alone, as normalize_identifier() reads it, and judged by
    :func:`licenseid.variants.decided`, the judge of every other path; its
    licence must be in *expression*, case ignored. An ID with the "+"
    operator after it states its grant, as the one reader of that operator
    (plusoperator.PLUS_OPERATOR) says: a "+" after a space or before a comma
    is none."""
    forms: list[str] = []
    words = {word.casefold() for word in RE_TOKEN.findall(expression)}
    granted = {
        plus.end("id") for plus in PLUS_OPERATOR.finditer(text) if not plus["with"]
    }
    for token in RE_TOKEN.finditer(text):
        # A bracket, a "+" or an operator is never decided; reading each
        # alone cost seconds on 40,000 brackets around one ID. Nor is a word
        # that is no bare or -with- deprecated ID: decided() is False for it
        # whatever its reading (decided(word, "") asks only that), so it is
        # not read again.
        if (
            token.end() in granted
            or not token.group(0)[0].isalnum()
            or not decided(token.group(0), "")
        ):
            continue
        reading = normalize_identifier(token.group(0), db)
        head = RE_TOKEN.findall(reading)[0].casefold()
        if decided(token.group(0), reading) and head in words:
            forms.append(head)
    return forms


def decide_ids(db: ListLookup, expression: str) -> str:
    """*expression* with each deprecated ID it states with no grant decided
    as the variant says, as :func:`licenseid.variants.decided` judges one: for
    an expression no marker reader takes ("GPL-3.0 WITH AdditionRef-x" is
    GPL-3.0-only WITH AdditionRef-x). An ID with the "+" operator after it is
    kept."""
    granted = {
        plus.end("id")
        for plus in PLUS_OPERATOR.finditer(expression)
        if not plus["with"]
    }

    def one(token: re.Match[str]) -> str:
        word = token.group(0)
        if token.end() in granted or not word[0].isalnum():
            return word
        reading = normalize_identifier(word, db)
        return reading if decided(word, reading) else word

    return RE_TOKEN.sub(one, expression)


# The deprecated IDs with an exception in them, case folded.
_WITH_IDS = frozenset(deprecated.casefold() for deprecated in DEPRECATED_WITH_IDS)


def read_inexactly(
    db: ListLookup, text: str, found: list[CandidateMatch], guessed: bool = False
) -> str | None:
    """How the first of *found*, the reading of the declared *text*, is not
    what *text* states, so is not exact, or None: ``"decided"`` for a
    deprecated ID decided as a form it does not state (:func:`decided_forms`,
    a guess to say),
    ``"ambiguous"`` for a "+" given to the licence of a deprecated ID with
    an exception in it ("GPL-2.0-with-classpath-exception+" read as
    GPL-2.0-or-later WITH Classpath-exception-2.0), which ``resolve()`` calls
    ambiguous (``deprecated_ambiguous``). *guessed*: a deprecated name was
    answered by the option (``variants.only_by_name``): decided."""
    if not found:
        return None
    forms = [] if guessed else decided_forms(db, text, found[0]["license_id"])
    if guessed or forms:
        # The forms the option chose: no word of the value states them.
        found[0].setdefault("evidence", Evidence())["decided"] = forms or variant_forms(
            found[0]["license_id"]
        )
        return "decided"
    for plus in PLUS_OPERATOR.finditer(text):
        if not plus["with"] and plus["id"].casefold() in _WITH_IDS:
            return "ambiguous"
    return None


# The word a licence's name may end in: "ISC License" is still one item.
_LICENCE_WORDS = frozenset(("license", "licence"))
# What joins the items of a list, beside "and" and "or".
_LIST_MARKS = frozenset(",;/&")


def disambiguate_whole(text: str, db: ListLookup) -> str | None:
    """:func:`disambiguate_deprecated_id` of *text*, a whole value (a field,
    a short text): None for no reading, ``""`` where ``resolve()`` refuses it,
    so no other reading answers: a mark before the grant (grant_follows:
    ``GPL-2.0; or later``), or another licence the value lists, which the
    answer would drop ("GPL-3.0, LGPL-2.1 or later", :func:`_lists_another`)."""
    first = bare_deprecated(text)
    if first is None:
        return None
    base, bare = first
    if grant_follows(base, text[bare.end() :]) is None:
        return ""  # "GPL-2.0: or later", which no phrase reads but the ID
    if _mark_glued_to_grant(text, bare.start()):
        return None  # "GPL-2.0 or later?": the author's doubt; resolve() says so
    found = disambiguate_deprecated_id(text)
    if found is None:
        return None
    return (
        "" if _lists_another(text, {base.casefold(), found.casefold()}, db) else found
    )


def _mark_glued_to_grant(text: str, start: int) -> bool:
    """Whether the first "or later" grant from *start* of *text* has a mark
    glued to its end that ``resolve()`` refuses (``dropguard.glued_marks``),
    after the words that may follow it ("version", "of the License")."""
    grant = OR_LATER_PHRASE.search(text, start)
    if grant is None:
        return False
    words = RE_GRANT_WORDS.match(text, grant.end())
    return bool(glued_marks(text, words.end() if words else grant.end()))


def _lists_another(text: str, own: set[str], db: ListLookup) -> bool:
    """Whether *text* lists a licence of the List that is not *own*: an ID
    that is an item of its own, joined to the rest by marks (",", ";", "/",
    "&") or "and"/"or" alone ("MIT, GPL-2.0 or later"), or one with a version
    in it, wherever it stands ("...; docs under the GFDL-1.3"). About 200 IDs
    are plain words too ("Copyright Intel Corp.", "the same as Ruby"): in
    prose they name no licence. The words are the expression's (RE_TOKEN)."""
    items: list[list[str]] = [[]]
    end = 0
    for token in RE_TOKEN.finditer(text):
        kind = token_kind(token[0])
        if kind == "OP" or not _LIST_MARKS.isdisjoint(text[end : token.start()]):
            items.append([])
        end = token.end()
        if kind == "ID":
            items[-1].append(token[0])
    return any(
        word.casefold() not in own
        and _names_a_licence(word, item)
        and db.get_license_details(word) is not None
        for item in items
        for word in item
    )


def _names_a_licence(word: str, item: list[str]) -> bool:
    """Whether *word*, of the list *item*, can name a licence there: it is
    the item alone (a last "License" aside: "ISC License"), or it has a
    version in it. An ID that is a plain word too ("Intel", "Zlib", "DOC")
    in prose names none."""
    words = [w for w in item if w.casefold() not in _LICENCE_WORDS] or item
    return len(words) == 1 or any(char.isdigit() for char in word)


def _item_after(text: str, start: int) -> list[str]:
    """The words of the list item of *text* that starts at *start*: up to
    a mark, "and" or "or" (the items of :func:`_lists_another`)."""
    words: list[str] = []
    end = start
    for token in RE_TOKEN.finditer(text, start):
        if token_kind(token[0]) == "OP" or not _LIST_MARKS.isdisjoint(
            text[end : token.start()]
        ):
            break
        words.append(token[0])
        end = token.end()
    return words


def before_grant(named: str) -> str:
    """*named*, the text of :func:`granted_id_text` or
    :func:`declared_grant_id_text`, without what opens its grant, by
    ``classify.grant_head``: white space (a no-break space too), "(" or "["
    and a dash between words. A dash joined to the ID (``GPL-2.0-or
    later``) stays, for the loose reading to judge."""
    head = grant_head(named)
    return named.rstrip(WHITE_SPACE) if head is None else head


def undashed_grant(value: str, head: str) -> str | None:
    """*value* without the dashes between words around the "or" of its
    grant, after *head* (:func:`before_grant`): "GPL-2.0 - or - later" is
    "GPL-2.0 or later". None if no dash stands there. A separator, which
    the reading records as a step; "or-later" is a word of its own."""
    gaps = _RE_GRANT_GAPS.match(value, len(head))
    if gaps is None:
        return None
    before, word, after = gaps.groups()
    spaced = _without_dashes(before), _without_dashes(after.strip(DASHES) and after)
    if spaced == ("", ""):
        return None
    return "".join(
        (
            value[: len(head)],
            spaced[0] or before,
            word,
            spaced[1] or after,  # "or-later" keeps its dash: a word of its own
            value[gaps.end() :],
        )
    )


def _without_dashes(gap: str) -> str:
    """*gap* without its dashes, each run of white space one space (at
    least one); "" if it has no dash, which leaves it as it is."""
    if gap == gap.translate(_NO_DASHES):
        return ""
    return _RE_WHITE_RUN.sub(" ", gap.translate(_NO_DASHES)) or " "


def drops_words(
    leading: str, expression: str, value: str, *, whole: bool, db: ListLookup
) -> bool:
    """Whether reading the declared *value* as *expression* (its *leading*
    expression, with a grant that follows it applied) would drop words that
    must not go: any words left over when the value is *whole* (a manifest
    field holds nothing else, so "MIT/Apache-2.0" is not MIT, and "GPL-2.0
    or later, and also MIT" is not GPL-2.0-or-later), words that state the
    qualifier of a "+" again (:func:`restates_qualifier`), or another
    licence of *db* listed after a mark (:func:`lists_another`). Only a
    grant that ends the value is no word left over (:func:`granted_id_text`,
    or :func:`declared_grant_id_text` for a bare "MIT or later")."""
    if leading == value:
        return False
    if lists_after_grant(db, leading, expression, value):
        return True  # a grant ending the value is no excuse: it is another's
    left = (
        expression == leading
        or (whole and trim_end_mark(value) is not None)  # a field's end mark is cut
        or (granted_id_text(value) is None and declared_grant_id_text(value) is None)
    )
    return left and (
        whole or restates_qualifier(leading, value) or lists_another(db, leading, value)
    )


def lists_after_grant(
    db: ListLookup, leading: str, expression: str, value: str
) -> bool:
    """Whether *value*, read as *expression* for its *leading* expression,
    lists another licence of *db* after the "or later" grant that follows
    *leading* (:func:`lists_another`, from the grant's end): in ``GPL-2.0 or
    later, ISC`` the grant ends the licence it qualifies, not the value, and
    an answer would drop ISC, also when another grant ends the value
    (``GPL-2.0 or later, ISC or later``). An operator after the grant
    (``MIT (or later) AND Apache-2.0``) or a mark glued to its end (``or
    later?``, as ``resolve()`` refuses; a comment closer is no mark) goes the
    same way, also an operator in brackets (``(AND MIT)``) and after end marks
    (``or later.; ISC``, ``or later., AND MIT``). ``GPL-2.0 or later,
    see COPYING`` and ``(see COPYING)`` keep their reading."""
    if expression == leading:
        return False  # no grant was applied (or only an "only")
    end = grant_stop(value, leading)
    if end is None:
        return False
    if glued_tag_marks(value, end):
        return True
    while end < len(value) and (value[end].isspace() or value[end] in ".:)]"):
        end += 1  # end marks and brackets hide neither an operator nor a listing
    if operator_at(value, end) is not None:
        return True
    return lists_another(db, value[:end], value)


def grant_stop(value: str, leading: str) -> int | None:
    """Where the grant after *leading*, the leading expression of *value*,
    ends with the words that may follow it ("version"), or None."""
    word = _RE_OR_WORD.search(value, len(leading.rstrip(")")))
    end = grant_end(value, word.start()) if word else None
    if end is None:
        return None
    words = RE_GRANT_WORDS.match(value, end)
    return words.end() if words else end


def operator_at(value: str, end: int) -> int | None:
    """Where an operator starts after *end* in *value*, past white space and
    an opening bracket (``(AND MIT)``) or a mark after an end mark (``., AND
    MIT``), or None."""
    peek = end
    while peek < len(value) and (
        value[peek].isspace()
        or value[peek] in "(["
        or (value[peek] in ",;" and value[peek - 1] in ".:")
    ):
        peek += 1
    return peek if RE_OPERATOR.match(value, peek) else None


def lists_another(db: ListLookup, leading: str, value: str) -> bool:
    """Whether *value* goes on after its *leading* expression with a mark
    SPDX has no operator for and a licence of *db* (``MIT/Apache-2.0``,
    ``MIT, LicenseRef-x``): the value lists both, and an answer of the
    first alone would drop the other (``resolve()``: ``not an SPDX
    operator``). The word after the mark is a reference, or an ID by the
    item rule of :func:`_lists_another`; prose keeps the reading (``MIT, see
    LICENSE``, ``Apache-2.0, Intel copyright``)."""
    listed = _RE_LISTED.match(value, len(leading))
    if listed is None:
        return False
    item = _item_after(value, listed.start(2))
    word = item[0] if item else ""
    if is_license_ref(word):
        return True
    return (
        token_kind(word) == "ID"
        and _names_a_licence(word, item)
        and names_only_listed(word, db)
    )


def restates_qualifier(expression: str, value: str) -> bool:
    """Whether *value* states again, after its leading *expression* that ends
    in the "+" operator, the qualifier the "+" states ("LGPL-2.1+ only",
    "GPL-2.0+ or later"). ``resolve()`` refuses such a value (``qualifier
    stated twice``), so no reading may answer it without the words that
    contradict it. An ID that ends in ``-only`` keeps its reading
    ("GPL-2.0-only or (at your option) any later version" is GPL-2.0-only
    in a tag, test_spdx_tag_adversarial)."""
    if (RE_TOKEN.findall(expression) or [""])[-1] != "+":
        return False
    rest = value[len(expression) :].lstrip()
    if ONLY_WORD.match(rest):
        return True
    return declared_grant_id_text(value) == expression.rstrip()


def variant_forms(expression: str) -> list[str]:
    """Every ``-only`` or ``-or-later`` ID of *expression*, folded."""
    return [
        word.casefold()
        for word in RE_TOKEN.findall(expression)
        if word.lower().endswith(("-only", "-or-later"))
    ]


def mark_guessed(match: CandidateMatch | RawMatch, written: str) -> None:
    """Mark the variant of *match*, read from *written*, as decided, not
    stated (its evidence lists the forms *decided*, so ``variant_stated`` is
    false and it is not exact), and say so: the DETAIL is the licence
    (``GPL-2.0``), not the text. Every variant of the match is decided where
    no reader listed the forms."""
    evidence = match.setdefault("evidence", Evidence())
    if "decided" not in evidence:
        evidence["decided"] = variant_forms(match["license_id"])
    resolved = match["license_id"]
    warn_guess(family_of(resolved, written), resolved)


def loose_with(db: ListLookup, text: str) -> tuple[str, str | None] | None:
    """*text*, a license written loosely WITH an exception, as an expression
    of the ID ("GPL2 WITH Classpath-exception-2.0" is GPL-2.0-only WITH
    Classpath-exception-2.0), and the loose license text if the variant of
    its licence was decided (the caller warns once the expression resolves).
    None if *text* is no such expression. The exception is the caller's to
    check. Brackets around the whole are no part of it ("(GPL2 WITH
    Classpath-exception-2.0)"), as for a declared expression. Any other
    bracket is none of this shape: WITH takes a license ID, not a bracketed
    one ("(GPL2) WITH x"), and an unbalanced one ("(GPL2 WITH x") is no
    expression.
    """
    inner = without_outer_brackets(text.strip())
    parts = WITH_OPERATOR.split(inner)
    if len(parts) != 2 or "(" in inner or ")" in inner:
        return None
    found = loose_id(db, parts[0])
    if found is None or " WITH " in found[1]:
        return None  # no license, or one that carries an exception already
    row, resolved = found
    loose = parts[0] if decided(row["license_id"], resolved) else None
    return f"{resolved} WITH {parts[1].strip()}", loose


def granted_id_text(text: str) -> str | None:
    """The part of *text* before an "or later" grant that ends it ("GPLv2 or
    any later version" gives "GPLv2 "), or None for a text without one. Read
    by the one reader of the phrase (classify.OR_LATER_PHRASE)."""
    grant = OR_LATER_PHRASE.search(text)
    if grant is None or not _RE_GRANT_TAIL.fullmatch(text, grant.end()):
        return None
    start = grant.start()
    if text[start].isdigit():  # the phrase starts at the version: "2 or later"
        word = _RE_GRANT_WORD.search(grant.group(0))
        start += word.start() if word else 0
    return text[:start]


# The word a declared grant starts with. Only a word boundary, so finding
# the last one is one pass over the text, whatever its white space.
_RE_OR_WORD = re.compile(r"\bor\b", re.IGNORECASE)


def declared_grant_id_text(text: str) -> str | None:
    """The part of a declared value before an "or later" grant that ends it,
    with or without a number before the grant: "GPL-3.0-only or later" and
    "GPL-3.0-only (or later)" give "GPL-3.0-only". None for a value without
    one.

    The grant starts at the last "or" after white space or a bracket, and
    classify.OR_LATER_PHRASE judges it. That reader wants a number before a
    bare "or later", as prose also says "sooner or later"; a declared value
    has its ID there, so the phrase is read as after a number, unless a
    negation takes it back."""
    last = None
    for last in _RE_OR_WORD.finditer(text):
        pass
    if last is None:
        return None
    named = grant_head(text[: last.start()])
    if named is None:
        return None
    end = grant_end(text, last.start())
    return named if end is not None and _RE_GRANT_TAIL.fullmatch(text, end) else None


def _granted(db: ListLookup, text: str) -> tuple[ListedName, str] | None:
    """*text* as a loose ID and an "or later" grant that ends it, read by the
    one reader of the phrase (classify.OR_LATER_PHRASE, through
    identifiers.qualify_trailing_grant): "GPLv2 or any later version" is
    GPL-2.0-or-later. None if the ID has no -or-later form: the grant is not
    dropped in silence, and the "+" it takes is the caller's to give (the
    leaf reader of resolve() gives it after the ID's deprecation)."""
    named = granted_id_text(text)
    if named is None:
        return None
    row = keyed_row(db, version_key(named))
    if row is None:
        return None
    lid = row["license_id"]
    or_later = qualify_trailing_grant(lid, f"{lid} {text[len(named) :]}")
    return None if or_later in (lid, f"{lid}+") else (row, or_later)
