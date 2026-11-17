# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The ``variant`` option of ``detect()`` (roadmap item 52): what to do where a
licence has a ``-only`` and an ``-or-later`` form and the input does not say
which (``GPL-2.0``, the text of the GPL).

``auto`` (the default) keeps a declared value as written (a bare ``GPL-2.0``
stays ``GPL-2.0``, as ``resolve()`` gives it) and never answers a deprecated
ID for a text: ``-or-later`` where the input grants it, else ``-only`` first
and ``-or-later`` second, with a warning. ``as-written`` never decides.
``only`` and ``or-later`` always decide, declared values too. The option is
a preference, never a fact: words that state the variant win, with a
warning.

:func:`stated_of` reads the ``variant_stated`` field of a result.
"""

import contextvars
import itertools
import re
from collections.abc import Callable, Iterator, MutableSequence, Sequence
from contextlib import contextmanager
from typing import Any, Final, TypeVar, cast

from licenseid.deprecatedids import (
    BARE_TO_OR_LATER,
    DEPRECATED_BARE_LICENSE_IDS,
    DEPRECATED_SPDX_LICENSE_IDS,
    DEPRECATED_WITH_IDS,
)
from licenseid.exprtokens import RE_TOKEN
from licenseid.grantsubject import GrantSignal, Signals
from licenseid.idoptions import excluded_ids
from licenseid.listlookup import fold_case
from licenseid.plusoperator import grant_stem
from licenseid.ranking import (
    TIE_WINDOW,
    only_signal,
    or_later_signal,
    leave_signal,
)
from licenseid.types import (
    CandidateMatch,
    DetectOptions,
    Evidence,
    InternalMatch,
    LicenseDetails,
    RawMatch,
    Variant,
)
from licenseid.variantstated import supports, times_written
from licenseid.warning import warn

_Match = TypeVar("_Match", RawMatch, CandidateMatch)

VARIANTS: Final[tuple[Variant, ...]] = ("auto", "as-written", "only", "or-later")
DEFAULT: Final[Variant] = "auto"

#: What a reader outside ``detect()`` (the library functions, the tests of a
#: reader) does as it always did: a bare ID is read as ``-only``.
_CURRENT: contextvars.ContextVar[Variant] = contextvars.ContextVar(
    "licenseid_variant", default="only"
)

#: The warnings of a ``detect()`` call, held until its first output result is
#: known (None outside a call: a warning is given at once), and the bar a
#: result must pass to be output (the CLI's ``--threshold`` and ``--exact``).
_PENDING: contextvars.ContextVar[list[tuple[str, str]] | None] = contextvars.ContextVar(
    "licenseid_variant_pending", default=None
)
_OUTPUT: contextvars.ContextVar[tuple[float, bool, int]] = contextvars.ContextVar(
    "licenseid_variant_output", default=(0.85, False, 1_000_000)
)

_BARE: Final = {fold_case(k): v for k, v in DEPRECATED_BARE_LICENSE_IDS.items()}
_WITH: Final = {fold_case(k): v for k, v in DEPRECATED_WITH_IDS.items()}
_OR_LATER_OF: Final = {fold_case(k): v for k, v in BARE_TO_OR_LATER.items()}
_OR_LATER_TWIN: Final = {fold_case(only): _OR_LATER_OF[k] for k, only in _BARE.items()}
_PLUS: Final = {fold_case(k): v for k, v in DEPRECATED_SPDX_LICENSE_IDS.items()}
#: A deprecated ID a text match never answers, and the ID that replaces it
#: (a ``-with-`` ID has no ID twin: it is an expression, decided alone).
_REPLACED_BY: Final = {
    **_BARE,
    **_PLUS,
}
#: The word "only", as a word of its own ("GPL-2.0 only", not "only if" in an
#: ID): the one reader of a stated ``-only``.
ONLY_WORD: Final = re.compile(r"(?<![\w-])only\b", re.IGNORECASE)
#: The score from which a guessed variant is worth saying: the 0.85 of
#: ``is_*()`` and the default ``--threshold``. Junk input scores 0.5 to 0.67
#: (a lorem ipsum, licence words shuffled) and answers nothing, and a guess
#: behind such an answer is no news.
ANSWER_SCORE: Final = 0.85
_TEXT_METHODS: Final = ("name", "text")
_ONLY: Final = "-only"
_OR_LATER: Final = "-or-later"


@contextmanager
def reading(variant: Variant) -> Iterator[None]:
    """Read every value in the block as *variant* says."""
    token = _CURRENT.set(variant)
    try:
        yield
    finally:
        _CURRENT.reset(token)


@contextmanager
def output_bar(threshold: float, exact_only: bool, top: int) -> Iterator[None]:
    """Within the block, a warning of ``detect()`` is for a result that
    ``--threshold``, ``--exact`` and ``--top`` let through: one that is
    printed."""
    token = _OUTPUT.set((threshold, exact_only, top))
    try:
        yield
    finally:
        _OUTPUT.reset(token)


def _output(
    found: Sequence[RawMatch | InternalMatch],
) -> list[RawMatch | InternalMatch]:
    """The results of *found* that the output bar lets through."""
    threshold, exact_only, top = _OUTPUT.get()
    return [
        r
        for r in found
        if round(min(r["score"], 1.0), 4) >= threshold
        and (
            not exact_only
            or (r["exact"] and not guessed_of(r["license_id"], r.get("evidence")))
        )
    ][:top]


def read_as(
    variant: Variant, produce: Callable[[], Sequence[RawMatch | InternalMatch]]
) -> Sequence[RawMatch | InternalMatch]:
    """What *produce* gives, read as *variant* says; the option is a
    preference, so the input that states a variant wins, and is said."""
    pending: list[tuple[str, str]] = []
    token = _PENDING.set(pending)
    try:
        with reading(variant):
            found = produce()
    finally:
        _PENDING.reset(token)
    shown = _output(found)  # a warning is for what is printed
    printed = [
        fold_case(t)
        for r in shown
        if guessed_of(r["license_id"], r.get("evidence"))
        for t in (*RE_TOKEN.findall(r["license_id"]), "|")  # "|" ends a result
    ]
    for family, answer in dict.fromkeys(pending):
        if _within([fold_case(t) for t in RE_TOKEN.findall(answer)], printed):
            warn("input", "variant not stated", family, f"using {answer}")
    for r in shown:
        warn_overridden(variant, r["license_id"], r.get("evidence"))
    return found


def fallback(lic_id: str) -> str | None:
    """What the bare or ``-with-`` deprecated ID *lic_id* is decided as, or
    None to keep it as written (``auto``, ``as-written``)."""
    return _decide(lic_id, _CURRENT.get())


def _decide(lic_id: str, variant: Variant) -> str | None:
    """:func:`fallback` for *variant*."""
    if variant in ("auto", "as-written"):
        return None
    key = fold_case(lic_id)
    with_id = _WITH.get(key)
    if with_id is not None:
        if variant == "only":
            return with_id
        return with_id.replace(_ONLY + " WITH ", _OR_LATER + " WITH ", 1)
    bare = _BARE.get(key)
    if bare is None:
        return None
    return bare if variant == "only" else _OR_LATER_OF.get(key)


def decided(row_id: str, resolved: str) -> bool:
    """Whether *resolved* is the variant licenseid chose for *row_id*, a bare
    or ``-with-`` deprecated ID: it was changed, which only :func:`fallback`
    does to such an ID."""
    key = fold_case(row_id)
    return (key in _BARE or key in _WITH) and fold_case(resolved) != key


def only_by_name(row: LicenseDetails, normalized: str) -> tuple[str, bool]:
    """What the List name of the deprecated ID of *row* answers (*normalized*
    is the ID as read outside ``detect()``), and whether that is a guess. A
    name that says "only" ("GNU General Public License v2.0 only") states
    ``-only``. Any other is a declaration of the ID: ``auto`` and ``as-written``
    keep it, ``only`` and ``or-later`` decide it, a guess."""
    lic_id = row["license_id"]
    only = _BARE.get(fold_case(lic_id))
    if only and ONLY_WORD.search(row["name"]):
        return only, False
    decided_id = _decide(lic_id, _CURRENT.get())  # None for auto, as-written
    return (decided_id, True) if decided_id else (normalized, False)


def family_of(resolved: str, written: str = "") -> str:
    """The licence of the first ``-only`` or ``-or-later`` ID of *resolved*
    that *written*, the value as it was, does not state (``LGPL-2.1`` of
    ``GPL-2.0-only OR LGPL-2.1-only`` read from ``GPL-2.0-only OR LGPL-2.1``),
    for a warning; *resolved* when it has none."""
    written_tokens = RE_TOKEN.findall(written)
    stated = {fold_case(t) for t in written_tokens}
    # "GPL-2.0+" states GPL-2.0-or-later
    stated |= {
        fold_case(t + _OR_LATER)
        for t, after in itertools.pairwise(written_tokens)
        if after == "+"
    }
    for token in RE_TOKEN.findall(resolved):
        if (
            token.lower().endswith((_ONLY, _OR_LATER))
            and fold_case(token) not in stated
        ):
            return grant_stem(token)
    return resolved


def read_from(found: list[_Match], value: str) -> list[_Match]:
    """*found*, the results of the declared *value* (an ID, a tag, a field),
    each with that value as the evidence of its variant."""
    for match in found:
        evidence = Evidence(value=value)
        marked = match.get("evidence", {}).get("decided")
        if marked is not None:  # the readers marked what they chose
            evidence["decided"] = marked
        match["evidence"] = evidence
    return found


def _within(part: list[str], whole: list[str]) -> bool:
    """Whether the tokens *part* stand together in the tokens *whole*."""
    n = len(part)
    return n > 0 and any(whole[i : i + n] == part for i in range(len(whole) - n + 1))


def _has_variant(token: str) -> bool:
    """Whether *token* is a List ID that names a variant (not a reference
    such as ``LicenseRef-acme-only``)."""
    key = token.lower()
    return key.endswith((_ONLY, _OR_LATER)) and "licenseref-" not in key


def _states(expression: str, evidence: Evidence | None) -> list[tuple[str, bool]]:
    """``(kind, stated)`` of each licence of *expression* that has a variant:
    ``bare`` (kept as written: never stated), ``only`` and ``later`` (an
    ``-only`` or ``-or-later`` ID, or an ID with a "+": stated if the
    *evidence* says so). A WITH target, a reference and ``MIT+`` have none."""
    tokens = RE_TOKEN.findall(expression)
    found: list[tuple[str, str, str]] = []  # (kind, family, form)
    for i, token in enumerate(tokens):
        key = fold_case(token)
        if i and tokens[i - 1].upper() == "WITH":
            continue  # an exception
        if i + 1 < len(tokens) and tokens[i + 1] == "+":
            if key in _BARE or key in _WITH or key in _OR_LATER_OF:
                found.append(("later", token, token + "+"))
        elif key in _BARE or key in _WITH:
            found.append(("bare", token, token))
        elif _has_variant(key):
            kind = "later" if key.endswith(_OR_LATER) else "only"
            found.append((kind, grant_stem(token), token))
    many = len({fold_case(f) for _, f, _ in found}) > 1
    return [
        (
            kind,
            kind != "bare" and supports((kind, family, form), evidence, many),
        )
        for kind, family, form in found
    ]


def stated_of(expression: str, evidence: Evidence | None) -> bool | None:
    """Whether the variant of *expression* is stated, as ``variant_stated``
    says it: None when no licence of it has a variant to judge (``MIT``);
    False when one is kept bare (``GPL-2.0``, ``GPL-2.0-with-x``) or, with no
    word of the *evidence* for it, decided by licenseid; else True."""
    states = _states(expression, evidence)
    return all(stated for _, stated in states) if states else None


def guessed_of(expression: str, evidence: Evidence | None) -> bool:
    """Whether *expression* has an ``-only`` or ``-or-later`` licence that
    the *evidence* does not state: a guess, so not exact."""
    return any(
        kind != "bare" and not stated for kind, stated in _states(expression, evidence)
    )


def _conflicts(variant: Variant, expression: str, evidence: Evidence | None) -> bool:
    """Whether *expression* states (by its *evidence*) a variant that
    *variant* does not ask."""
    wrong = {"only": "later", "or-later": "only"}.get(variant)
    return any(
        kind == wrong and stated for kind, stated in _states(expression, evidence)
    )


def warn_overridden(
    variant: Variant, expression: str, evidence: Evidence | None
) -> None:
    """Say that the input states a variant that the option *variant* asks
    otherwise for, once the answer *expression* is known: it wins."""
    if _conflicts(variant, expression, evidence):
        warn(
            "option",
            "overridden by input",
            f"--variant {variant}",
            f"using {expression}",
        )


def warn_guess(family: str, used: str) -> None:
    """Say that *family* was answered as *used*, its variant not stated: at
    once, or (within ``detect()``) if *used* is in its first output result."""
    held = _PENDING.get()
    if held is not None:
        held.append((family, used))
        return
    warn("input", "variant not stated", family, f"using {used}")


def _head(license_id: str) -> str:
    """*license_id* without its exception: ``GPL-2.0-only`` for
    ``GPL-2.0-only WITH Classpath-exception-2.0``."""
    return re.split(r"\s+WITH\s+", license_id, maxsplit=1, flags=re.IGNORECASE)[0]


def _is_variant_id(license_id: str) -> bool:
    return _head(license_id).lower().endswith((_ONLY, _OR_LATER))


def settle_free_text(
    results: Sequence[RawMatch | InternalMatch],
    text: str,
    is_pure: bool,
    options: DetectOptions,
) -> list[RawMatch | InternalMatch]:
    """:func:`settle_text` of the *results* for *text*, the input, as it
    grants later versions or states "only" (:func:`licenseid.ranking.
    or_later_signal`, :func:`licenseid.ranking.only_signal`), read as the
    ``variant`` of *options* says."""
    written = {id(r): r["license_id"] for r in results}
    out = settle_text(
        list(results),
        Signals(
            or_later_signal(text, is_pure),
            only_signal(text, is_pure),
            leave_signal(text, is_pure),
        ),
        options.get("variant", DEFAULT),
        written=text,
    )
    # A form the option chose comes after ``exclude`` ran: it may not be an
    # excluded one (a hint, added after that filter, stays). A bare ID it
    # decided is dropped, an ``-only`` it moved to ``-or-later`` stays.
    excluded = excluded_ids(options.get("exclude") or [])
    kept = []
    for r in out:
        before = written.get(id(r), r["license_id"])
        if before != r["license_id"] and fold_case(r["license_id"]) in excluded:
            if not _is_variant_id(before):
                continue
            r["license_id"] = before
            if r["score"] >= ANSWER_SCORE:  # the guess now is the ``-only``
                warn_guess(grant_stem(_head(before)), before)
        kept.append(r)
    return kept


def settle_text(
    results: MutableSequence[RawMatch | InternalMatch],
    signals: Signals,
    variant: Variant,
    *,
    written: str = "",
) -> list[RawMatch | InternalMatch]:
    """The results of a text or name match, settled for *variant*:
    never a deprecated ID unless ``as-written``; a ``-only``/``-or-later``
    result carries the evidence of its variant: *signals*, the input's grant of
    the licence's later versions, chose ``-or-later``, the input states
    *only* of it, or *written* (the input) holds the ID itself (a marker found
    it); an ``-or-later`` answer no grant of the input chose, none written, is
    settled to its ``-only`` twin (not for ``or-later``); the ``or-later``
    option puts that form first where nothing is stated; the answer that is a
    guess is said once, if it is an answer (:data:`ANSWER_SCORE`)."""
    signal, only, leave = signals
    out = _replaced(list(results), variant, written)
    if variant == "as-written":  # a licence with nothing stated: the bare ID
        out = _collapsed(out, lambda lid: signal(lid) or only(lid))
    if variant != "or-later":
        _ungranted_to_only(out, signal, written, leave)
    scores = {fold_case(r["license_id"]): r["score"] for r in out}
    for r in out:
        if r["method"] in _TEXT_METHODS:
            lid = r["license_id"]
            r["evidence"] = Evidence(
                value=written,
                later=_chosen_by(r, scores) and signal(lid),
                only=_is_only(r) and not signal(lid) and only(lid),
            )
    if variant == "or-later" and out:
        first = out[0]["license_id"]
        if not (signal(first) or only(first)):
            _prefer_or_later(out)  # nothing stated of the licence
    top = out[0] if out else None
    if (
        top
        and _is_variant_id(top["license_id"])
        and guessed_of(top["license_id"], top.get("evidence"))
        and top["score"] >= ANSWER_SCORE
    ):
        warn_guess(grant_stem(_head(top["license_id"])), top["license_id"])
    return out


def _ungranted_to_only(
    results: list[RawMatch | InternalMatch],
    signal: GrantSignal,
    written: str,
    leave: Callable[[], bool],
) -> None:
    """Settle an ``-or-later`` top of a text or name match to its ``-only``
    twin where the input grants none of that licence and the ID is not written
    in it: the match took "or later" from words that are not the licence's
    (``Requires Python 3.8 or later``). Left alone where *leave* says so: a
    later-version phrase with no subject (``or any version later``), or a pure
    licence text."""
    top = results[0] if results else None
    if top is None or top["method"] not in _TEXT_METHODS:
        return
    lid = top["license_id"]
    head = _head(lid)
    if (
        not head.lower().endswith(_OR_LATER)
        or signal(lid)
        or times_written(head, written)
        or leave()
    ):
        return
    twin = f"{grant_stem(head)}{_ONLY}{lid[len(head) :]}"
    for j, other in enumerate(results[1:], 1):
        if fold_case(other["license_id"]) == fold_case(twin):
            top["score"], other["score"] = other["score"], top["score"]
            results[0], results[j] = other, top
            return
    top["license_id"] = twin


def _is_only(r: RawMatch | InternalMatch) -> bool:
    return _head(r["license_id"]).lower().endswith(_ONLY)


def _chosen_by(r: RawMatch | InternalMatch, scores: dict[str, float]) -> bool:
    """Whether the grant of the input chose *r*: an ``-or-later`` result
    that does not rank below its ``-only`` peer (within the tie window the
    tie-breaker moved apart), or has none. One the text matches worse than
    its peer is the text's doing, not the grant's."""
    lid = r["license_id"]
    head = _head(lid)
    if not head.lower().endswith(_OR_LATER):
        return False
    peer = scores.get(fold_case(f"{grant_stem(head)}{_ONLY}{lid[len(head) :]}"))
    return peer is None or r["score"] + 2 * TIE_WINDOW > peer


def _replaced(
    results: list[RawMatch | InternalMatch], variant: Variant, written: str = ""
) -> list[RawMatch | InternalMatch]:
    """*results* without the deprecated IDs that a replacement is among
    (except for ``as-written``): the replacement takes the better score,
    so a deprecated ID a marker found does not lose its answer. A deprecated
    ID the option decides becomes its form, or merges with the result of
    that form."""
    if variant == "as-written":
        return list(results)
    by_id = {fold_case(r["license_id"]): r for r in results}
    out = []
    for r in results:
        # A marker found the ID (the input holds it): a declared one, which
        # the option decides alone, whatever a retrieved twin scored.
        twin = _REPLACED_BY.get(fold_case(r["license_id"]))
        kept = by_id.get(fold_case(twin)) if twin else None
        if r["method"] in _TEXT_METHODS and times_written(r["license_id"], written):
            kept = None
        if kept is None and r["method"] in _TEXT_METHODS:
            # No replacement beside it (a marker found the ID): the option
            # decides it, as for a declared value.
            decided_id = _decide(r["license_id"], variant)
            if decided_id:
                same = by_id.get(fold_case(decided_id))
                if same is not None and same is not r:
                    same["score"] = max(same["score"], r["score"])
                    continue
                r["license_id"] = decided_id
                by_id[fold_case(decided_id)] = r
        if kept is None or r["method"] not in _TEXT_METHODS:
            out.append(r)
        else:
            kept["score"] = max(kept["score"], r["score"])
    out.sort(key=lambda r: -r["score"])
    return out


def _collapsed(
    results: list[RawMatch | InternalMatch],
) -> list[RawMatch | InternalMatch]:
    """*results*, the two twins of a licence beside its bare ID (a tie, as
    they share one text) left as the bare ID, which says no more than the
    input does."""
    ids = {fold_case(r["license_id"]): r for r in results}
    drop: set[str] = set()
    for key, bare in _BARE.items():
        row = ids.get(key)
        twins = (ids.get(fold_case(bare)), ids.get(fold_case(_OR_LATER_OF[key])))
        if (
            row is None
            or None in twins
            or row["method"] not in _TEXT_METHODS
            or stated(row["license_id"])
        ):
            continue
        first = next(t for t in twins if t)
        row["score"] = max(row["score"], *(t["score"] for t in twins if t))
        row["exact"] = row["exact"] or any(t["exact"] for t in twins if t)
        cast(Any, row).update(
            similarity=first["similarity"], coverage=first["coverage"]
        )
        drop |= {fold_case(t["license_id"]) for t in twins if t}
    out = [r for r in results if fold_case(r["license_id"]) not in drop]
    out.sort(key=lambda r: -r["score"])
    return out


def _prefer_or_later(results: list[RawMatch | InternalMatch]) -> None:
    """Move an ``-only`` top the option chose (the input does not state it)
    to its ``-or-later`` form."""
    if results and guessed_of(results[0]["license_id"], results[0].get("evidence")):
        _move_to_later(results)


def _move_to_later(results: list[RawMatch | InternalMatch]) -> None:
    """Put the ``-or-later`` form first where the top is an ``-only``, the two
    scores swapped so the list stays in score order; where none was retrieved
    (a heading names the ``-only`` form alone), the form the List pairs with
    it."""
    lid = results[0]["license_id"]
    head = _head(lid)
    if not head.lower().endswith(_ONLY):
        return
    peer = f"{grant_stem(head)}{_OR_LATER}{lid[len(head) :]}".lower()
    for j, other in enumerate(results[1:], 1):
        if other["license_id"].lower() == peer:
            top = results[0]
            top["score"], other["score"] = other["score"], top["score"]
            results[0], results[j] = other, top
            return
    later = _OR_LATER_TWIN.get(fold_case(head))
    if later:
        results[0]["license_id"] = f"{later}{lid[len(head) :]}"


_ONLY_NEXT = re.compile(r"\s+only\b(?!\s+if\b)", re.IGNORECASE | re.ASCII)
_ONLY_THEN_OPERATOR = re.compile(
    r"\s+only\s+(?:and|or|with)\b", re.IGNORECASE | re.ASCII
)


def qualify_trailing_only(expression: str, value: str) -> str:
    """*expression* with the bare deprecated ID it ends in read ``-only``,
    when the word right after it in *value* says so ("GPL-2.0 only"): the
    variant is stated, so it is no guess and ``variant`` leaves it. ``""``, no
    reading, for what it would drop: an operator after the "only", or an AND
    or OR before the ID (the "only" would say it of one operand)."""
    tokens = RE_TOKEN.findall(expression)
    only = _BARE.get(fold_case(tokens[-1])) if tokens else None
    rest = value[len(expression) :] if value.startswith(expression) else ""
    if only and expression.endswith(tokens[-1]) and _ONLY_NEXT.match(rest):
        listed = any(token.upper() in ("AND", "OR") for token in tokens)
        if listed or _ONLY_THEN_OPERATOR.match(rest):
            return ""
        return expression[: -len(tokens[-1])] + only
    return expression
