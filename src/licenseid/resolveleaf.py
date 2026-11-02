# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The single-value reading of the resolver: one declared value, one licence.

:func:`read_leaf` reads a value that names one licence (an ID, a listed
name, a loosely written ID, a ``+`` or an "or later" grant, with its
exception if it has one) and records in a :class:`Found` the expression, the
steps taken, the expansions it declined to apply and the candidates.
``resolver.match`` calls it once for the whole declared value; the
compound reader calls it once for each operand. It refuses a licence or an
exception longer than ``MAX_KEY_INPUT`` (no ID is longer), but not a control
character or an over-long value: the caller refuses those first, as
``match`` does. It reads the list through
:class:`licenseid.listlookup.ListLookup` alone and knows nothing of the
database, of brackets around the whole value, or of an expression of several
licences. The gate covers each half of a WITH (decision Q16), so a long
licence name with an exception (``Creative Commons Attribution Non
Commercial No Derivatives 2.5 Generic WITH RRDtool-FLOSS-exception-2.0``) is
read.
"""

import re
from dataclasses import dataclass, field

from licenseid.dropguard import (
    code_points,
    dropped,
    dropped_words,
    ends_in_ref,
    joined_marks,
    trim_end_mark,
)
from licenseid.errors import one_line
from licenseid.exprtokens import is_addition_ref, is_license_ref
from licenseid.identifiers import without_outer_brackets
from licenseid.listlookup import ListLookup
from licenseid.looseid import (
    WITH_OPERATOR,
    declared_grant_id_text,
    granted_id_text,
    loose_id,
)
from licenseid.resolvereason import after_bracket, on_reference, stated_twice
from licenseid.resolvertypes import (
    CATEGORY_ORDER,
    LEXICAL_KINDS,
    Category,
    Step,
    step,
)
from licenseid.versionkey import MAX_KEY_INPUT

_RE_NUMBERS = re.compile(r"\d+(?:\.\d+)*")
_RE_VERSION = re.compile(r"[vV]?\d+(?:\.\d+)*")
# Brackets other than around the whole value: "[MIT]", "MIT)" are no ID.
_RE_BRACKET = re.compile(r"[()\[\]{}]")
# Characters that end a value after its last "+": white space and "+" itself.
# Runs only after read_leaf's MAX_KEY_INPUT gate, so its run is bounded.
_RE_TRAILING = re.compile(r"[\s+]+\Z")
# A step kind that is not also a category name, mapped to the one it counts as.
_AS_CATEGORY = {kind: "lexical" for kind in LEXICAL_KINDS}


@dataclass
class Found:
    """What the lookup decided, before it is put in the public shape."""

    expression: str | None = None
    steps: list[Step] = field(default_factory=list)
    expansions: list[Step] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    category: Category | None = None  # set where the lookup knows better
    reason: str | None = None  # why nothing was resolved, where the lookup knows
    # The weakest category a step before the leaf allows (a stray quote mark
    # makes any answer at most ``separator``), whatever its step kind is.
    floor: Category | None = None


def category_of(found: Found) -> Category:
    """The category of a reading: the one the lookup set, else the weakest
    kind among its steps, its expansions and its floor (``exact`` for none)."""
    if found.category is not None:
        return found.category
    kinds = {_AS_CATEGORY.get(s["kind"], s["kind"]) for s in found.steps}
    if found.floor is not None:
        kinds.add(found.floor)
    kinds |= {s["kind"] for s in found.expansions}
    ranked = [c for c in CATEGORY_ORDER if c in kinds]
    return ranked[-1] if ranked else "exact"


class _Dropped(Exception):
    """A loose reading would drop a character that says something (see
    :mod:`licenseid.dropguard`): the whole value is refused, not read."""

    def __init__(
        self, text: str, lost: str, license_id: str, *, words: bool = False
    ) -> None:
        super().__init__(text)
        self.text = text
        self.lost = lost
        self.license_id = license_id
        self.words = words  # *lost* is words, else characters

    def record(self, found: Found) -> None:
        """Make *found* the refusal: ``unresolved``, a ``drop`` step that did
        not apply (the reading it stopped), and the reason."""
        # Reset what a half-read value may have put in *found* before the
        # exception: a refusal answers no expression, no candidate, and no
        # step but its own.
        found.expression = None
        found.category = "unresolved"
        detail = one_line(self.lost) if self.words else code_points(self.lost)
        found.reason = f"{'word' if self.words else 'character'} dropped: {detail}"
        found.steps = [step("drop", False, self.text, self.license_id, detail)]
        found.expansions = []
        found.candidates = []


def refuse_dropped(found: Found, text: str, lost: str, license_id: str) -> None:
    """Make *found* the refusal of *text*, which a reading as *license_id*
    would leave the characters *lost* off: ``unresolved`` with a ``drop``
    step and the reason ``character dropped: U+...``."""
    _Dropped(text, lost, license_id).record(found)


def read_leaf(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text* as one licence (with its exception, if any) into *found*.
    False if it names none, or if the licence or the exception is longer
    than any ID (:func:`over_key_cap`). True with ``unresolved`` and a
    ``reason`` if a loose reading would drop a character that says something
    (``Apache 2.0?``).

    One ``;`` or ``:`` at the end (``MIT;``) is an ending, not a mark that
    says something: when the value is refused for it, it is read again
    without it, with a ``separator`` step (P77). So is any one end mark
    after a ``+``, an exception or a ``LicenseRef-*``, where no loose
    reading ran to refuse it, and any other mark there is refused as after
    an ID (P80)."""
    if over_key_cap(text):
        return False
    read = _read(db, text, found)
    if not read:
        return _after_core(db, text, found)
    if found.expression is None and found.reason is not None:
        _read_without_end(db, text, trim_end_mark(text, ";:"), found)
    return read


def _read_without_end(
    db: ListLookup, text: str, trimmed: str | None, found: Found
) -> bool:
    """Read *text* again as *trimmed*, which is *text* without its one end
    mark (None for no such mark), if that names a licence: *found* is then
    the reading, after an ending ``separator`` step."""
    again = Found()
    if trimmed is None or not _read(db, trimmed, again) or not again.expression:
        return False
    found.expression, found.category = again.expression, again.category
    found.steps = [step("separator", True, text, trimmed, "end mark")]
    found.steps += again.steps
    found.expansions, found.candidates = again.expansions, again.candidates
    found.reason = None
    return True


def _after_core(db: ListLookup, text: str, found: Found) -> bool:
    """A value no reader read, that ends in marks after a ``+``, an exception
    or a ``LicenseRef-*`` (P80): those readers return before the drop guard.
    One end mark is an ending, read without it; marks that say something
    (``GPL-2.0+?``, ``MIT+;;``) refuse the value, as they do after an ID.
    False when the value is not of that shape or its core names nothing."""
    body = text.rstrip()
    ended = trim_end_mark(body)
    if ended is not None and _is_core(ended):
        return _read_without_end(db, text, ended, found)
    lost = (set(dropped(body)) | set(joined_marks(body))) - set("+()[]{}")
    core = body
    # A ``-``, ``.`` or ``_`` that ends a ``LicenseRef-*`` belongs to the ID
    while core and core[-1] in lost and not (core[-1] in ".-" and ends_in_ref(core)):
        core = core[:-1].rstrip()
    again = Found()
    if core == body or not _is_core(core) or not _read(db, core, again):
        return False
    if again.expression is None:
        return False
    marks = "".join(dict.fromkeys(c for c in body[len(core) :] if c in lost))
    refuse_dropped(found, text, marks, again.expression)
    return True


def _is_core(core: str) -> bool:
    """Whether *core* is of the shape :func:`_after_core` handles."""
    return bool(core) and (
        core.endswith("+")
        or WITH_OPERATOR.search(core) is not None
        or is_license_ref(core)
    )


def _read(db: ListLookup, text: str, found: Found) -> bool:
    """:func:`read_leaf` without the cap and the ending of the value."""
    try:
        return _with(db, text, found) or _one(db, text, found)
    except _Dropped as refusal:
        refusal.record(found)
        return True


def over_key_cap(text: str) -> bool:
    """Whether the licence or the exception of *text* (each half of a WITH,
    else the whole) is longer than MAX_KEY_INPUT, so names no ID (decision
    Q16). A ``LicenseRef-*`` or ``AdditionRef-*`` is exempt: SPDX sets no
    length on one, and it is read as written, never through a key."""
    halves = WITH_OPERATOR.split(text)
    return any(
        len(half) > MAX_KEY_INPUT
        and not is_license_ref(half.strip())
        and not is_addition_ref(half.strip())
        for half in (halves if len(halves) == 2 else [text])
    )


def _one(db: ListLookup, text: str, found: Found) -> bool:
    """*text* as one licence: with a "+", else as an ID, a name or a grant."""
    return (text.endswith("+") and _plus(db, text, found)) or _single(db, text, found)


def _with(db: ListLookup, text: str, found: Found) -> bool:
    """``X WITH exception``: X read as a value of its own (a "+", a grant, a
    loose ID), the exception by its ID. False unless the exception is listed
    and X names a licence; a malformed or unresolved X makes the whole so."""
    operator = WITH_OPERATOR.search(text)
    parts = WITH_OPERATOR.split(text)
    if operator is None or len(parts) != 2:
        return False
    licence_text, exception_text = _grant_to_licence(parts[0], parts[1])
    licence, tail = Found(), Found()
    exception = _exception(db, exception_text, tail)
    if exception is None or not _one(db, licence_text, licence):
        return False
    if licence.expression is None:
        found.category, found.reason = licence.category, licence.reason
        return True
    found.steps.extend(_with_form(text, operator) + licence.steps + tail.steps)
    found.expansions.extend(licence.expansions + tail.expansions)
    found.expression = f"{licence.expression} WITH {exception}"
    found.candidates = [f"{c} WITH {exception}" for c in licence.candidates]
    return True


def _grant_to_licence(licence: str, exception: str) -> tuple[str, str]:
    """The licence and the exception of a WITH, an "or later" grant after
    the exception moved to the licence: it qualifies the licence, not the
    exception ("GPL-2.0 WITH Classpath-exception-2.0 or later" grants GPL-2.0
    or later), as an SPDX tag reads it (identifiers.qualify_trailing_grant)."""
    named = granted_id_text(exception) or declared_grant_id_text(exception)
    if named is None:
        return licence, exception
    core = named.rstrip(" \t([")
    return f"{licence} {exception[len(core) :].strip()}", core


def _with_form(text: str, operator: re.Match[str]) -> list[Step]:
    """The steps that give the WITH of *text* its form: an ``operator_case``
    step for ``with`` in other case, a ``whitespace`` step for other spacing
    around it (a tab, two spaces), so that ``exact`` means the input is the
    expression (decision Q17)."""
    steps = []
    before, after = text[: operator.start()], text[operator.end() :]
    cased = before + operator.group(0).upper() + after
    if cased != text:
        steps.append(step("operator_case", True, text, cased))
    spaced = f"{before} WITH {after}"
    if spaced != cased:
        steps.append(step("whitespace", True, cased, spaced))
    return steps


def _exception(db: ListLookup, text: str, found: Found) -> str | None:
    """The listed exception *text* names, its case and its deprecation read
    as for a licence (_deprecation), or None. An ``AdditionRef-*`` names
    itself, as written and unchecked, as a ``LicenseRef-*`` does (Q20)."""
    if is_addition_ref(text):
        return text
    details = db.get_exception_details(text)
    if details is None:
        return None
    exception_id = details["exception_id"]
    if exception_id != text:
        found.steps.append(step("id_case", True, text, exception_id))
    if not details["is_deprecated"]:
        return exception_id
    successor = details.get("superseded_by")
    if successor:
        found.steps.append(
            step("deprecated_equal_successor", True, exception_id, successor)
        )
        return successor
    found.expansions.append(
        step("deprecated_ambiguous", False, exception_id, exception_id)
    )
    return exception_id


def _plus(db: ListLookup, text: str, found: Found) -> bool:
    """``X+`` as ``X-or-later`` where the List has that ID. Otherwise ``X+`` as
    written, after the deprecation of ``X`` (a rename is followed, an ID with
    no known successor is offered, not changed). A qualifier already stated
    (``X-only+``, ``X++``, ``X + +``) is malformed. Nothing is recorded in
    *found* unless the value names a licence."""
    core = _RE_TRAILING.sub("", text)
    spacing = []
    stripped = text[:-1].rstrip()
    if stripped != text[:-1]:
        spacing.append(step("whitespace", True, text, stripped + "+"))
    if stripped.endswith(")"):  # a "+" follows a license ID, not a bracket
        inner = without_outer_brackets(stripped).strip()
        return _malformed_if_named(db, inner, found, after_bracket(text))
    base = _base(db, stripped)
    if base is None:
        doubled = text[len(core) :].count("+") > 1
        return doubled and _malformed_if_named(db, core, found, stated_twice(text))
    license_id, steps = base
    if license_id.endswith(("-only", "-or-later", "+")) or is_license_ref(license_id):
        # The qualifier is stated, and "+" adds a second; a LicenseRef takes none.
        found.category = "malformed"
        found.reason = (on_reference if is_license_ref(license_id) else stated_twice)(
            text
        )
        return True
    found.steps.extend(spacing + steps)
    or_later = f"{license_id}-or-later"
    if _in_use(db, or_later):
        found.expansions.append(step("plus_to_or_later", True, text, or_later))
        found.expression = _canonical(db, or_later)
        return True
    _deprecation(db, license_id, found)
    found.expression = f"{found.expression}+"
    return True


def _malformed_if_named(db: ListLookup, text: str, found: Found, reason: str) -> bool:
    """Mark *found* malformed, for *reason*, if *text* names a licence, whose
    qualifier the caller found broken; False if it names none."""
    if _base(db, text) is None:
        return False
    found.category, found.reason = "malformed", reason
    return True


def _single(db: ListLookup, text: str, found: Found) -> bool:
    """A value that names one licence: a stated qualifier ("GPLv2 or later"),
    or an ID, a name or a loose ID, then its deprecation."""
    named = granted_id_text(text) or declared_grant_id_text(text)
    if named is not None:
        named = named.rstrip(" \t([")  # "GPL-3.0 (or later)": the "(" is the grant's
        if _qualified(db, named):
            found.category, found.reason = "malformed", stated_twice(text)
            return True
        base = _base(db, named.strip())
        if base is not None:
            return _grant(db, text, base, found)
    base = _base(db, text)
    if base is None:
        return False
    found.steps.extend(base[1])
    _deprecation(db, base[0], found)
    return True


def _qualified(db: ListLookup, named: str) -> bool:
    """Whether *named*, a licence before an "or later" grant, states a
    qualifier already: a grant ("X or later or later") or a "+" ("GPLv3+ or
    later"). A stated "-only" or "-or-later" is _grant's to refuse."""
    twice = declared_grant_id_text(named) or granted_id_text(named)
    if twice is not None:
        return _base(db, twice.rstrip(" \t([")) is not None
    core = _RE_TRAILING.sub("", named)
    return core != named and _base(db, core) is not None


def _grant(
    db: ListLookup, text: str, base: tuple[str, list[Step]], found: Found
) -> bool:
    """An ID followed by an "or later" grant. The grant is applied where the
    List has the ``-or-later`` ID; a qualifier already stated (``X-only or
    later``) is malformed. An ID with no ``-or-later`` form takes the grant
    as the SPDX "+" operator (``Apache 2.0 or later`` is ``Apache-2.0+``,
    decision Q14), after its deprecation, as ``X+`` is read, whether or not
    its ID has a version (``MIT or later`` is ``MIT+``; P35, decided by the
    maintainer on 2026-10-29). A ``LicenseRef-*`` takes no "+" (invalid
    SPDX) and is unresolved, not read without the grant."""
    license_id, steps = base
    granted = loose_id(db, text)
    # "+" last: `_qualified` makes `X+ or later` malformed before this, so
    # it only guards a list that has an ID ending in "+" (`Foo+`, no `Foo`)
    if license_id.endswith(("-only", "-or-later", "+")):
        found.category, found.reason = "malformed", stated_twice(text)
        return True
    if granted is None and is_license_ref(license_id):
        found.category, found.reason = "unresolved", on_reference(text)
        return True
    found.steps.extend(steps)
    if granted is None:
        _deprecation(db, license_id, found)
        expression = f"{found.expression}+"
    else:
        expression = granted[1]
    found.expansions.append(
        step("stated_qualifier", True, text, expression, "or later stated")
    )
    found.expression = expression
    return True


def _base(db: ListLookup, text: str) -> tuple[str, list[Step]] | None:
    """The listed ID *text* names, and the steps from *text* to it: its own
    ID in other case, a listed name, or a loosely written ID. A
    ``LicenseRef-*`` names itself. Raises :class:`_Dropped` where the loose
    reading would drop a character that says something."""
    if is_license_ref(text):
        return text, []
    details = db.get_license_details(text)
    if details is not None:
        license_id = details["license_id"]
        same = license_id == text
        return license_id, [] if same else [step("id_case", True, text, license_id)]
    names = db.get_active_ids_by_name().get(text.casefold(), [])
    if len(names) == 1:
        return names[0], [step("listed_name", True, text, names[0])]
    if "+" in text or _RE_BRACKET.search(text):
        return None  # "+" and brackets are read by the caller, not folded away
    loose = loose_id(db, text)
    if loose is None:
        return None
    license_id = loose[0]["license_id"]
    lost = dropped(text)
    if lost:
        raise _Dropped(text, lost, license_id)
    lost = dropped_words(text)
    if lost:
        raise _Dropped(text, lost, license_id, words=True)
    return license_id, _spelling(text, license_id)


def _spelling(text: str, license_id: str) -> list[Step]:
    """The steps from a loose *text* to the *license_id* it names: its form
    (``separator``), its number (``version_spelling``), or both. What was
    applied is read back from the two strings; it does not decide the match."""
    steps = []
    skeleton = _RE_VERSION.sub("#", text).casefold()
    if skeleton != _RE_VERSION.sub("#", license_id).casefold():
        steps.append(step("separator", True, text, license_id))
    if _RE_NUMBERS.findall(text) != _RE_NUMBERS.findall(license_id):
        steps.append(step("version_spelling", True, text, license_id))
    return steps or [step("separator", True, text, license_id)]


def _deprecation(db: ListLookup, license_id: str, found: Found) -> None:
    """Set the expression for the listed *license_id*, following a rename and
    declining to narrow a split ID."""
    details = db.get_license_details(license_id)
    if details is None or not details.get("is_deprecated"):
        found.expression = license_id
        return
    successor = details.get("superseded_by")
    if successor:
        found.steps.append(
            step("deprecated_equal_successor", True, license_id, successor)
        )
        found.expression = _canonical(db, successor)
        return
    found.expression = license_id
    found.candidates = sorted(
        c for c in (f"{license_id}-only", f"{license_id}-or-later") if _in_use(db, c)
    )
    kind = "assumed_only" if found.candidates else "deprecated_ambiguous"
    found.expansions.append(step(kind, False, license_id, license_id))


def _in_use(db: ListLookup, license_id: str) -> bool:
    """Whether *license_id* is a licence of the List that is not deprecated."""
    details = db.get_license_details(license_id)
    return details is not None and not details.get("is_deprecated")


def _canonical(db: ListLookup, license_id: str) -> str:
    """The List's spelling of *license_id*; the argument if it is not listed."""
    details = db.get_license_details(license_id)
    return details["license_id"] if details else license_id
