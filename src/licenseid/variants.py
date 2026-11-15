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
import re
from collections.abc import Callable, Iterator, MutableSequence, Sequence
from contextlib import contextmanager
from typing import Any, Final, cast

from licenseid.deprecatedids import (
    BARE_TO_OR_LATER,
    DEPRECATED_BARE_LICENSE_IDS,
    DEPRECATED_SPDX_LICENSE_IDS,
    DEPRECATED_WITH_IDS,
)
from licenseid.exprtokens import RE_TOKEN
from licenseid.listlookup import fold_case
from licenseid.plusoperator import grant_stem
from licenseid.ranking import TIE_WINDOW, only_signal, or_later_signal
from licenseid.types import DetectOptions, InternalMatch, RawMatch, Variant
from licenseid.warning import warn

VARIANTS: Final[tuple[Variant, ...]] = ("auto", "as-written", "only", "or-later")
DEFAULT: Final[Variant] = "auto"

#: What a reader outside ``detect()`` (the library functions, the tests of a
#: reader) does as it always did: a bare ID is read as ``-only``.
_CURRENT: contextvars.ContextVar[Variant] = contextvars.ContextVar(
    "licenseid_variant", default="only"
)

_BARE: Final = {fold_case(k): v for k, v in DEPRECATED_BARE_LICENSE_IDS.items()}
_WITH: Final = {fold_case(k): v for k, v in DEPRECATED_WITH_IDS.items()}
_OR_LATER_OF: Final = {fold_case(k): v for k, v in BARE_TO_OR_LATER.items()}
_PLUS: Final = {fold_case(k): v for k, v in DEPRECATED_SPDX_LICENSE_IDS.items()}
#: A deprecated ID a text match never answers, and the ID that replaces it.
_REPLACED_BY: Final = {
    **_BARE,
    **{k: v.split(" WITH ")[0] for k, v in _WITH.items()},
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


def read_as(
    variant: Variant, produce: Callable[[], Sequence[RawMatch | InternalMatch]]
) -> Sequence[RawMatch | InternalMatch]:
    """What *produce* gives, read as *variant* says; the option is a
    preference, so the input that states a variant wins, and is said."""
    with reading(variant):
        found = produce()
    if found and found[0]["score"] >= ANSWER_SCORE:  # else nothing is printed
        top = found[0]
        warn_overridden(variant, top["license_id"], top.get("variant_guessed", False))
    return found


def fallback(lic_id: str) -> str | None:
    """What the bare or ``-with-`` deprecated ID *lic_id* is decided as, or
    None to keep it as written (``auto``, ``as-written``)."""
    variant = _CURRENT.get()
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


def only_by_name(name: str, lic_id: str) -> str:
    """*lic_id*, a bare deprecated ID that a List name says is ``-only``
    ("GNU General Public License v2.0 only"), as its ``-only`` twin: the name
    states the variant."""
    only = _BARE.get(fold_case(lic_id))
    return only if only and ONLY_WORD.search(name) else lic_id


def family_of(resolved: str, written: str = "") -> str:
    """The licence of the first ``-only`` or ``-or-later`` ID of *resolved*
    that *written*, the value as it was, does not state (``LGPL-2.1`` of
    ``GPL-2.0-only OR LGPL-2.1-only`` read from ``GPL-2.0-only OR LGPL-2.1``),
    for a warning; *resolved* when it has none."""
    stated = {fold_case(t) for t in RE_TOKEN.findall(written)}
    for token in RE_TOKEN.findall(resolved):
        if (
            token.lower().endswith((_ONLY, _OR_LATER))
            and fold_case(token) not in stated
        ):
            return grant_stem(token)
    return resolved


def stated_of(expression: str, guessed: bool) -> bool | None:
    """Whether the variant of *expression* is stated, as ``variant_stated``
    says it: None when no licence of it has a variant to judge (``MIT``);
    False when one is kept bare (``GPL-2.0``, ``GPL-2.0-with-x``) or, with
    *guessed*, decided by licenseid; else True (an ``-only`` or ``-or-later``
    ID, or an ID with a "+")."""
    states: list[bool] = []
    tokens = RE_TOKEN.findall(expression)
    for i, token in enumerate(tokens):
        key = fold_case(token)
        if i and tokens[i - 1].upper() == "WITH":
            continue  # an exception
        if i + 1 < len(tokens) and tokens[i + 1] == "+":
            states.append(not guessed)  # the "+" states "or later"
        elif key in _BARE or key in _WITH:
            states.append(False)
        elif key.endswith((_ONLY, _OR_LATER)):
            states.append(not guessed)
    return None if not states else all(states)


def _conflicts(variant: Variant, expression: str) -> bool:
    """Whether *expression* states a variant that *variant* does not ask."""
    tokens = [t.lower() for t in RE_TOKEN.findall(expression)]
    later = "+" in tokens or any(t.endswith(_OR_LATER) for t in tokens)
    only = any(t.endswith(_ONLY) for t in tokens)
    return later if variant == "only" else only if variant == "or-later" else False


def warn_overridden(variant: Variant, expression: str, guessed: bool) -> None:
    """Say that the input states a variant that the option *variant* asks
    otherwise for, once the answer *expression* is known: it wins."""
    if not guessed and _conflicts(variant, expression):
        warn(
            "option",
            "overridden by input",
            f"--variant {variant}",
            f"using {expression}",
        )


def warn_guess(family: str, used: str) -> None:
    """Say that *family* was answered as *used*, its variant not stated."""
    warn("input", "variant not stated", family, f"using {used}")


def _is_variant_id(license_id: str) -> bool:
    return license_id.lower().endswith((_ONLY, _OR_LATER))


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
    return settle_text(
        list(results),
        or_later_signal(text, is_pure),
        options.get("variant", DEFAULT),
        only=only_signal(text, is_pure),
    )


def settle_text(
    results: MutableSequence[RawMatch | InternalMatch],
    signal: bool,
    variant: Variant,
    *,
    only: bool = False,
) -> list[RawMatch | InternalMatch]:
    """The results of a text or name match, settled for *variant*:
    never a deprecated ID unless ``as-written``; a ``-only``/``-or-later``
    result is marked guessed (``variant_guessed``) unless *signal*, the
    input's grant of the licence's later versions, chose ``-or-later``, or
    the input states *only*; the ``or-later`` option puts that form first
    where nothing is stated; the answer that is a guess is said once, if it
    is an answer (:data:`ANSWER_SCORE`)."""
    out = _replaced(list(results), variant)
    if variant == "as-written" and not (signal or only):
        out = _collapsed(out)  # nothing stated: the bare ID says no more
    scores = {fold_case(r["license_id"]): r["score"] for r in out}
    for r in out:
        if r["method"] in _TEXT_METHODS and _is_variant_id(r["license_id"]):
            stated = _chosen_by(r, scores) if signal else only and _is_only(r)
            r["variant_guessed"] = not stated
        elif r["method"] in _TEXT_METHODS and fold_case(r["license_id"]) in _PLUS:
            r["variant_guessed"] = True  # "GPL-2.0+" the List names, not the input
    if variant == "or-later" and not (signal or only):
        _prefer_or_later(out)
    top = out[0] if out else None
    if (
        top
        and top.get("variant_guessed")
        and _is_variant_id(top["license_id"])
        and top["score"] >= ANSWER_SCORE
    ):
        warn_guess(grant_stem(top["license_id"]), top["license_id"])
    return out


def _is_only(r: RawMatch | InternalMatch) -> bool:
    return r["license_id"].lower().endswith(_ONLY)


def _chosen_by(r: RawMatch | InternalMatch, scores: dict[str, float]) -> bool:
    """Whether the grant of the input chose *r*: an ``-or-later`` result
    that does not rank below its ``-only`` peer (within the tie window the
    tie-breaker moved apart), or has none. One the text matches worse than
    its peer is the text's doing, not the grant's."""
    lid = r["license_id"]
    if not lid.lower().endswith(_OR_LATER):
        return False
    peer = scores.get(fold_case(f"{grant_stem(lid)}{_ONLY}"))
    return peer is None or r["score"] + 2 * TIE_WINDOW > peer


def _replaced(
    results: list[RawMatch | InternalMatch], variant: Variant
) -> list[RawMatch | InternalMatch]:
    """*results* without the deprecated IDs that a replacement is among
    (except for ``as-written``): the replacement takes the better score,
    so a deprecated ID a marker found does not lose its answer."""
    if variant == "as-written":
        return list(results)
    by_id = {fold_case(r["license_id"]): r for r in results}
    out = []
    for r in results:
        twin = _REPLACED_BY.get(fold_case(r["license_id"]))
        kept = by_id.get(fold_case(twin)) if twin else None
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
        if row is None or None in twins or row["method"] not in _TEXT_METHODS:
            continue
        first = next(t for t in twins if t)
        row["score"] = max(row["score"], *(t["score"] for t in twins if t))
        row["exact"] = any(t["exact"] for t in twins if t)
        cast(Any, row).update(
            similarity=first["similarity"], coverage=first["coverage"]
        )
        drop |= {fold_case(t["license_id"]) for t in twins if t}
    out = [r for r in results if fold_case(r["license_id"]) not in drop]
    out.sort(key=lambda r: -r["score"])
    return out


def _prefer_or_later(results: list[RawMatch | InternalMatch]) -> None:
    """Put the ``-or-later`` form first where it follows its ``-only`` peer
    at the top, the two scores swapped so the list stays in score order."""
    if not results or not results[0]["license_id"].lower().endswith(_ONLY):
        return
    peer = f"{grant_stem(results[0]['license_id'])}{_OR_LATER}".lower()
    for j, other in enumerate(results[1:], 1):
        if other["license_id"].lower() == peer:
            top = results[0]
            top["score"], other["score"] = other["score"], top["score"]
            results[0], results[j] = other, top
            return


_ONLY_NEXT = re.compile(r"\s+only\b(?!\s+if\b)", re.IGNORECASE | re.ASCII)


def qualify_trailing_only(expression: str, value: str) -> str:
    """*expression* with the bare deprecated ID it ends in read ``-only``,
    when the word right after it in *value* says so ("GPL-2.0 only"): the
    variant is stated, so it is no guess and ``variant`` leaves it."""
    tokens = RE_TOKEN.findall(expression)
    only = _BARE.get(fold_case(tokens[-1])) if tokens else None
    rest = value[len(expression) :] if value.startswith(expression) else ""
    if only and expression.endswith(tokens[-1]) and _ONLY_NEXT.match(rest):
        return expression[: -len(tokens[-1])] + only
    return expression
