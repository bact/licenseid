# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The ID lists of ``detect()``, ``exclude`` and ``hint``, read by one rule.

Both act on free text only (a declaration is never filtered or hinted). An ID
in either compares case-folded (``listlookup.fold_case``: IDs are case
insensitive, as the database looks them up). A bare deprecated ID
(``GPL-2.0``) is ambiguous between its two twins, so it stands for both, and
a warning says so; ``GPL-2.0+`` stands for ``GPL-2.0-or-later``, as the List
reads a "+". A deprecated ``-with-`` ID has no twin to stand for (its
successor is an expression) and is taken as written.
"""

from collections.abc import Iterable

from licenseid.deprecatedids import BARE_TO_OR_LATER, DEPRECATED_BARE_LICENSE_IDS
from licenseid.listlookup import fold_case
from licenseid.plusoperator import strip_plus_operator
from licenseid.types import DetectOptions, RawMatch
from licenseid.warning import warn

# Folded bare ID: (the ID as written, its -only twin, its -or-later twin).
_TWINS: dict[str, tuple[str, str, str]] = {
    fold_case(bare): (bare, only, BARE_TO_OR_LATER[bare])
    for bare, only in DEPRECATED_BARE_LICENSE_IDS.items()
}


def folded(ids: Iterable[str]) -> frozenset[str]:
    """The IDs of *ids*, case-folded, to compare an ID by."""
    return frozenset(fold_case(i) for i in ids)


def excluded_ids(ids: Iterable[str]) -> frozenset[str]:
    """The IDs *ids* exclude, case-folded. A deprecated ID that free text can
    still name (a title "GPL-2.0", "GPL-2.0+") goes with its twins: it is
    excluded when named, or when both twins are (the "+" form with
    ``-or-later``)."""
    out = set(folded(ids))
    for bare, (_, only, or_later) in _TWINS.items():
        twins = {fold_case(only), fold_case(or_later)}
        if bare in out:
            out |= twins
        if twins <= out:
            out.add(bare)
        if fold_case(or_later) in out:
            out.add(bare + "+")
    return frozenset(out)


def free_text_hits(matches: list[RawMatch], excluded: Iterable[str]) -> list[RawMatch]:
    """The *matches* of a short text that its name tier found, without an
    excluded ID. A match with no similarity is a declaration resolve() read:
    never dropped."""
    return [
        m
        for m in matches
        if m.get("similarity") is None or fold_case(m["license_id"]) not in excluded
    ]


def _upgraded(option: str, ids: Iterable[str], *, keep_bare: bool) -> list[str]:
    """*ids* with each bare deprecated ID replaced by its two twins; one
    warning for each such ID, however often or in whatever case it is
    given. With *keep_bare* (``variant="as-written"``) a bare ID stays as
    written, silently; a "+" still states "or later"."""
    out: list[str] = []
    warned: set[str] = set()
    for given in ids:
        stem = strip_plus_operator(given)  # "GPL-2.0+": the "+" operator
        twins = _TWINS.get(fold_case(stem))
        if twins is None:
            out.append(given)
            continue
        if keep_bare and stem == given:
            out.append(given)
            continue
        bare, only, or_later = twins
        # The List reads "X+" as X-or-later; a bare ID stands for both twins.
        used = (or_later,) if stem != given else (only, or_later)
        out.extend(used)
        written = bare + "+" if stem != given else bare
        if fold_case(written) in warned:
            continue
        warned.add(fold_case(written))
        warn(
            "option", "deprecated ID", f"{option} {written}", f"using {', '.join(used)}"
        )
    return out


def upgraded_options(options: DetectOptions) -> DetectOptions:
    """*options* with the bare deprecated IDs of ``exclude`` and ``hint``
    upgraded (and warned of; kept for ``as-written``). Other keys, and an
    option not given, as they are."""
    result = DetectOptions(**options)
    keep = options.get("variant") == "as-written"
    if exclude := options.get("exclude"):
        result["exclude"] = _upgraded("exclude", exclude, keep_bare=keep)
    if hint := options.get("hint"):
        result["hint"] = _upgraded("hint", hint, keep_bare=keep)
    return result
