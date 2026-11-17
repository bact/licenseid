# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The ``variant`` option of ``detect()`` and ``--variant`` (roadmap item
52): a declared value stays as written under ``auto``, a text never answers a
deprecated ID, ``only`` and ``or-later`` decide, stated words win, and
``variant_stated`` says which. Inputs x variants x paths."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import time
from collections.abc import Generator
from typing import Any

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from timing import slack

from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.errors import InvalidInputError
from licenseid.grantsubject import Signals, constant
from licenseid.ranking import only_signal, or_later_signal
from licenseid.types import Evidence, InternalMatch, Method, RawMatch, Variant
from licenseid.variants import (
    _states,
    family_of,
    qualify_trailing_only,
    read_as,
    settle_text,
    warn_guess,
)

GPL_TEXT = (
    "GNU GENERAL PUBLIC LICENSE Version 2 June 1991 The licenses for most "
    "software are designed to take away your freedom to share and change it "
    "By contrast the GNU General Public License is intended to guarantee your "
    "freedom to share and change free software to make sure the software is "
    "free for all its users"
)
ROWS = (
    Lic(
        "GPL-2.0-only", "GNU General Public License v2.0 only", True, True, True
    )._replace(search_text=GPL_TEXT),
    Lic(
        "GPL-2.0-or-later", "GNU General Public License v2.0 or later", True, True, True
    )._replace(search_text=GPL_TEXT),
    Lic(
        "GPL-2.0", "GNU General Public License v2.0", False, is_deprecated=True
    )._replace(search_text=GPL_TEXT),
    Lic("MIT", "MIT License", True, True, True),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),
    Lic("GPL-3.0-only", "GNU General Public License v3.0 only", True, True, True),
    Lic("GPL-3.0-or-later", "GNU General Public License v3.0 or later"),
    Lic("GPL-3.0", "GNU General Public License v3.0", False, is_deprecated=True),
    Lic("GPL-2.0-with-classpath-exception", "w/Classpath", False, is_deprecated=True),
    Lic(
        "GPL-2.0+",
        "GNU General Public License v2.0 or later",
        False,
        is_deprecated=True,
    ),
)


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    yield from seeded_db("test_variant", ROWS, ["Classpath-exception-2.0"])


def _detect(
    db: str, given: GivenWarnings, variant: str | None = None, **inp: Any
) -> tuple[list[tuple[str, bool, bool | None]], list[str]]:
    options: dict[str, Any] = {} if variant is None else {"variant": variant}
    found = LicenseDetector(db).detect(**inp, **options)
    return (
        [(r["expression"], r["exact"], r["variant_stated"]) for r in found],
        [str(w) for w in given.take()],
    )


NOT_STATED = "input: variant not stated: GPL-2.0; using GPL-2.0-only"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MIT", ("MIT", True, None)),
        ("GPL-2.0", ("GPL-2.0", True, False)),
        ("GPL-2.0+", ("GPL-2.0-or-later", True, True)),
        ("GPL-2.0 or later", ("GPL-2.0-or-later", True, True)),
        ("GPL-2.0-only", ("GPL-2.0-only", True, True)),
        ("GPL-2.0-or-later", ("GPL-2.0-or-later", True, True)),
        ("MIT OR GPL-2.0", ("GPL-2.0 OR MIT", True, False)),
        ("MIT OR GPL-2.0-only", ("GPL-2.0-only OR MIT", True, True)),
        ("MIT OR Apache-2.0", ("Apache-2.0 OR MIT", True, None)),
        ("GPL-2.0 AND GPL-2.0-only", ("GPL-2.0 AND GPL-2.0-only", True, False)),
        ("GPL-2.0-with-classpath-exception", None),
    ],
)
@pytest.mark.parametrize("via", ["text", "license_id", "tag", "field"])
def test_a_declared_value_stays_as_written_under_auto(
    db: str,
    given: GivenWarnings,
    via: str,
    value: str,
    expected: tuple[Any, ...] | None,
) -> None:
    if via == "license_id" and " " in value:
        pytest.skip("--id declares one licence")
    inp: dict[str, Any] = {
        "text": {"text": value},
        "license_id": {"license_id": value},
        "tag": {"text": f"# SPDX-License-Identifier: {value}\n"},
        "field": {"text": f'{{"license": "{value}"}}'},
    }[via]
    if expected is None:  # a deprecated -with- ID: kept, its flags the twin's
        kept = LicenseDetector(db).detect(**inp)
        assert [(r["expression"], r["variant_stated"]) for r in kept] == [
            (value, False)
        ]
    else:
        found, warned = _detect(db, given, **inp)
        assert (found[0], warned) == (expected, [])


@pytest.mark.parametrize(
    ("variant", "value", "expected", "warned"),
    [
        ("auto", "GPL-2.0", ("GPL-2.0", True, False), []),
        ("as-written", "GPL-2.0", ("GPL-2.0", True, False), []),
        ("only", "GPL-2.0", ("GPL-2.0-only", False, False), [NOT_STATED]),
        (
            "or-later",
            "GPL-2.0",
            ("GPL-2.0-or-later", False, False),
            ["input: variant not stated: GPL-2.0; using GPL-2.0-or-later"],
        ),
        (
            "only",
            "MIT OR GPL-3.0",
            ("GPL-3.0-only OR MIT", False, False),
            ["input: variant not stated: GPL-3.0; using GPL-3.0-only OR MIT"],
        ),
        ("only", "MIT", ("MIT", True, None), []),
        (
            "only",
            "GPL-2.0-with-classpath-exception",
            ("GPL-2.0-only WITH Classpath-exception-2.0", False, False),
            [
                (
                    "input: variant not stated: GPL-2.0; "
                    "using GPL-2.0-only WITH Classpath-exception-2.0"
                )
            ],
        ),
        # What the input states wins: the option is a preference.
        (
            "only",
            "GPL-2.0+",
            ("GPL-2.0-or-later", True, True),
            ["option: overridden by input: --variant only; using GPL-2.0-or-later"],
        ),
        (
            "only",
            "GPL-2.0 or later",
            ("GPL-2.0-or-later", True, True),
            ["option: overridden by input: --variant only; using GPL-2.0-or-later"],
        ),
        (
            "or-later",
            "GPL-2.0-only",
            ("GPL-2.0-only", True, True),
            ["option: overridden by input: --variant or-later; using GPL-2.0-only"],
        ),
        ("only", "GPL-2.0-only", ("GPL-2.0-only", True, True), []),
        ("or-later", "GPL-2.0-or-later", ("GPL-2.0-or-later", True, True), []),
        (
            "only",
            "GPL-2.0-with-classpath-exception+",
            ("GPL-2.0-or-later WITH Classpath-exception-2.0", False, True),
            [
                (
                    "option: overridden by input: --variant only; "
                    "using GPL-2.0-or-later WITH Classpath-exception-2.0"
                )
            ],
        ),
    ],
)
@pytest.mark.parametrize("via", ["text", "license_id", "tag"])
def test_variant_decides_a_declared_value(  # pylint: disable=R0913,R0917
    db: str,
    given: GivenWarnings,
    via: str,
    variant: Variant,
    value: str,
    expected: tuple[Any, ...],
    warned: list[str],
) -> None:
    inp = {
        "text": {"text": value},
        "license_id": {"license_id": value},
        "tag": {"text": f"# SPDX-License-Identifier: {value}\n"},
    }[via]
    if via == "license_id" and " " in value:
        pytest.skip("--id declares one licence")
    found, got = _detect(db, given, variant, **inp)
    assert (found[0], got) == (expected, warned)


def _hit(license_id: str, score: float, method: Method = "text") -> RawMatch:
    return RawMatch(
        license_id=license_id,
        method=method,
        exact=False,
        score=score,
        similarity=score,
        coverage=1.0,
    )


def _flag(r: RawMatch | InternalMatch) -> bool | None:
    """True for a variant licenseid chose, False for one the input states,
    None for a result with no variant to judge or a bare ID kept."""
    states = _states(r["license_id"], r.get("evidence"))
    judged = [stated for kind, stated in states if kind != "bare"]
    return None if not judged else not all(judged)


def _settle(
    hits: list[RawMatch | InternalMatch],
    signal: bool,
    variant: Variant,
    given: GivenWarnings,
) -> tuple[list[tuple[str, bool | None]], list[str]]:
    out = settle_text(hits, Signals(constant(signal)), variant)
    return (
        [(r["license_id"], _flag(r)) for r in out],
        [str(w) for w in given.take()],
    )


GPL = ("GPL-2.0-only", "GPL-2.0-or-later")


@pytest.mark.parametrize(
    ("hits", "signal", "variant", "expected", "warned"),
    [
        # No grant: -only first, both guessed, one warning.
        (
            [(GPL[0], 1.0), (GPL[1], 1.0)],
            False,
            "auto",
            [(GPL[0], True), (GPL[1], True)],
            [NOT_STATED],
        ),
        # A grant chose -or-later: stated, and nothing to warn of.
        (
            [(GPL[1], 0.99), (GPL[0], 0.98)],
            True,
            "auto",
            [(GPL[1], False), (GPL[0], True)],
            [],
        ),
        # --variant or-later puts it first where nothing states it.
        (
            [(GPL[0], 1.0), (GPL[1], 0.995)],
            False,
            "or-later",
            [(GPL[1], True), (GPL[0], True)],
            ["input: variant not stated: GPL-2.0; using GPL-2.0-or-later"],
        ),
        (
            [(GPL[0], 1.0), (GPL[1], 0.995)],
            False,
            "only",
            [(GPL[0], True), (GPL[1], True)],
            [NOT_STATED],
        ),
        # An -or-later that the text matches worse than its peer is no grant's doing.
        (
            [(GPL[0], 0.95), (GPL[1], 0.80)],
            True,
            "auto",
            [(GPL[0], True), (GPL[1], True)],
            [NOT_STATED],
        ),
        # A deprecated ID is never answered, whatever its score.
        (
            [("GPL-2.0", 1.0), (GPL[0], 0.99), (GPL[1], 0.99), ("GPL-2.0+", 0.98)],
            False,
            "auto",
            [(GPL[0], True), (GPL[1], True)],
            [NOT_STATED],
        ),
        # as-written never decides: the two twins collapse to the bare ID.
        (
            [(GPL[0], 0.99), (GPL[1], 0.99), ("GPL-2.0", 0.97)],
            False,
            "as-written",
            [("GPL-2.0", None)],
            [],
        ),
        # A deprecated ID a marker scored better than its twin lends the score.
        (
            [("GPL-2.0", 0.855), (GPL[0], 0.505), (GPL[1], 0.5)],
            False,
            "auto",
            [(GPL[0], True), (GPL[1], True)],
            [NOT_STATED],
        ),
        # A "+" ID the List names, found by name, is no statement of the input.
        ([("GPL-2.0+", 0.9, "name")], False, "as-written", [("GPL-2.0+", True)], []),
        # A guess behind a poor match is not worth saying.
        (
            [(GPL[0], 0.6), (GPL[1], 0.6)],
            False,
            "auto",
            [(GPL[0], True), (GPL[1], True)],
            [],
        ),
        # A licence with no variant is untouched.
        ([("MIT", 1.0)], False, "auto", [("MIT", None)], []),
        # A family with no bare ID.
        (
            [("GFDL-1.3-invariants-only", 1.0), ("GFDL-1.3-invariants-or-later", 1.0)],
            False,
            "auto",
            [
                ("GFDL-1.3-invariants-only", True),
                ("GFDL-1.3-invariants-or-later", True),
            ],
            [
                (
                    "input: variant not stated: GFDL-1.3-invariants; "
                    "using GFDL-1.3-invariants-only"
                )
            ],
        ),
    ],
)
def test_a_text_is_settled_by_its_grant_and_the_variant(  # pylint: disable=R0913,R0917
    given: GivenWarnings,
    hits: list[tuple[Any, ...]],
    signal: bool,
    variant: Variant,
    expected: list[tuple[str, bool | None]],
    warned: list[str],
) -> None:
    got = _settle([_hit(*h) for h in hits], signal, variant, given)
    assert got == (expected, warned)


def test_a_name_hit_is_settled_like_a_text_and_a_declaration_is_not(
    given: GivenWarnings,
) -> None:
    named = _hit(GPL[0], 1.0, "name")
    declared = _hit(GPL[0], 1.0, "id")
    declared["exact"] = True
    declared["evidence"] = Evidence(value=GPL[0])  # the ID is in the value
    assert _settle([named], False, "auto", given)[0] == [(GPL[0], True)]
    assert _settle([declared], False, "auto", given) == ([(GPL[0], False)], [])


@pytest.mark.parametrize("pure", [True, False])
def test_the_appendix_of_a_pure_text_is_no_grant(pure: bool) -> None:
    """The GPL's "How to Apply" appendix holds the phrase: a pure licence
    text is never read for a grant."""
    appendix = "either version 2 of the License, or (at your option) any later version"
    assert or_later_signal(f"{GPL_TEXT} {appendix}", pure)("GPL-2.0-only") is (not pure)


def test_a_name_without_its_grant_answers_only_first(
    db: str, given: GivenWarnings
) -> None:
    found, warned = _detect(db, given, text="GNU General Public License v2.0")
    assert [e for e, _, _ in found[:2]] == ["GPL-2.0-only", "GPL-2.0-or-later"]
    assert warned == [NOT_STATED]
    assert not {e for e, _, _ in found} & {"GPL-2.0", "GPL-2.0+"}


@pytest.mark.parametrize("bad", ["Only", "", "auto ", "x" * 80])
def test_an_unknown_variant_is_refused(db: str, bad: str) -> None:
    with pytest.raises(InvalidInputError, match="^option: invalid: variant: "):
        LicenseDetector(db).detect("MIT", variant=bad)  # type: ignore[arg-type]


def test_a_variant_that_is_no_str_is_a_type_error(db: str) -> None:
    with pytest.raises(TypeError, match="variant must be str, not int"):
        LicenseDetector(db).detect("MIT", variant=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("args", "code", "out", "err"),
    [
        (["--variant", "only", "GPL-2.0"], 0, "GPL-2.0-only\n", NOT_STATED),
        (["--variant=or-later", "--id", "GPL-2.0"], 0, "GPL-2.0-or-later\n", None),
        (["--variant", "as-written", "GPL-2.0"], 0, "GPL-2.0\n", ""),
        (["GPL-2.0"], 0, "GPL-2.0\n", ""),
        (["--variant", "nope", "MIT"], 2, "", None),
    ],
)
@pytest.mark.terse_cli
def test_the_cli_takes_variant(
    db: str, args: list[str], code: int, out: str, err: str | None
) -> None:
    result = CliRunner().invoke(cli, ["--db", db, "detect", *args])
    assert (result.exit_code, result.stdout) == (code, out)
    stderr = "".join(
        line for line in result.stderr.splitlines(True) if "days old" not in line
    )
    if err is not None:
        assert stderr == (f"WARNING: {err}\n" if err else "")
    elif code == 2:
        assert stderr == (
            "ERROR: option: invalid: --variant: nope; "
            "use one of auto, as-written, only, or-later\n"
        )


def test_the_variant_stated_field_prints_last() -> None:
    from licenseid.result import no_detection_line

    assert no_detection_line().endswith("\tCOVERAGE=\tVARIANT_STATED=")


def test_as_written_keeps_the_better_score_and_exactness_of_the_twins(
    given: GivenWarnings,
) -> None:
    twins = [_hit(GPL[0], 1.0), _hit(GPL[1], 1.0)]
    for twin in twins:
        twin["exact"] = True
    (bare,) = settle_text(
        [*twins, _hit("GPL-2.0", 0.97)], Signals(constant(False)), "as-written"
    )
    assert (bare["license_id"], bare["score"], bare["exact"]) == ("GPL-2.0", 1.0, True)
    assert not given.take()


@pytest.mark.parametrize(
    ("resolved", "written", "family"),
    [
        ("GPL-2.0-only", "GPL-2.0", "GPL-2.0"),
        ("GPL-2.0-only OR LGPL-2.1-only", "GPL-2.0-only OR LGPL-2.1", "LGPL-2.1"),
        ("MIT", "MIT", "MIT"),
    ],
)
def test_the_warning_names_the_licence_that_was_decided(
    resolved: str, written: str, family: str
) -> None:
    assert family_of(resolved, written) == family


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("GPL-2.0 only", "GPL-2.0-only"),
        ("GPL-2.0 only if you agree", "GPL-2.0"),  # a condition, no statement
        ("gpl-2.0 only", "GPL-2.0-only"),  # the ID in any case
        ("GPL-2.0 only OR MIT", ""),  # an operator ends no expression: refused
        ("GPL-2.0 only and MIT", ""),
    ],
)
def test_a_stated_only_after_an_id(value: str, expression: str) -> None:
    assert qualify_trailing_only(value.split(" ")[0], value) == expression


def test_the_only_reader_does_not_backtrack() -> None:
    """A long run of version numbers is read in one pass."""
    text = "Table of versions: " + "1." * 40_000
    start = time.monotonic()
    assert only_signal(text, False)("GPL-2.0-only") is False
    assert only_signal(text + " version 2 only", False)("GPL-2.0-only") is True
    assert time.monotonic() - start < slack(1.0)


@pytest.mark.parametrize(
    ("signal", "only", "first"),
    [(True, False, "GPL-2.0-or-later"), (False, True, "GPL-2.0-only")],
)
def test_as_written_keeps_a_stated_variant_of_a_text(
    given: GivenWarnings, signal: bool, only: bool, first: str
) -> None:
    """The twins fold to the bare ID only where the input states nothing."""
    other = "GPL-2.0-only" if signal else "GPL-2.0-or-later"
    hits: list[RawMatch | InternalMatch] = [
        _hit(first, 0.97),
        _hit(other, 0.96),
        _hit("GPL-2.0", 0.96),
    ]
    out = settle_text(hits, Signals(constant(signal), constant(only)), "as-written")
    assert (out[0]["license_id"], _flag(out[0])) == (first, False)
    assert not given.take()


def test_an_override_nothing_printed_for_is_not_warned(given: GivenWarnings) -> None:
    weak = _hit("GPL-3.0-or-later", 0.6)
    read_as("only", lambda: [weak])
    assert not given.take()


@pytest.mark.parametrize(
    ("hit", "variant", "expected", "warned"),
    [
        # A marker found the ID itself: the input states it.
        ("GPL-2.0-or-later", "auto", ("GPL-2.0-or-later", False), []),
        ("GPL-2.0-only", "auto", ("GPL-2.0-only", False), []),
        # A bare ID with no twin beside it is decided by the option.
        ("GPL-2.0", "only", ("GPL-2.0-only", True), ["GPL-2.0"]),
        ("GPL-2.0", "or-later", ("GPL-2.0-or-later", True), ["GPL-2.0"]),
        ("GPL-2.0", "auto", ("GPL-2.0", None), []),
    ],
)
def test_an_id_a_marker_found_is_stated_or_decided(
    given: GivenWarnings,
    hit: str,
    variant: Variant,
    expected: tuple[str, bool | None],
    warned: list[str],
) -> None:
    text = f"## License\n\n{hit}\n"
    out = settle_text(
        [_hit(hit, 0.92)], Signals(constant(False)), variant, written=text
    )
    assert (out[0]["license_id"], _flag(out[0])) == expected
    assert len(given.take()) == len(warned)


@pytest.mark.parametrize(
    ("args", "said"),
    [
        (["--variant", "only", "GPL-2.0"], True),
        (["--variant", "only", "--exact", "GPL-2.0"], False),  # not printed
        (["--variant", "only", "--top", "1", "GPL-2.0 OR MIT"], True),
        (["--variant", "only", "--threshold", "1", "GPL-2.0"], True),
        (["--variant", "only", "--exact", "GPL-2.0-or-later"], True),  # printed
        (["--exact", "--text", GPL_TEXT], False),  # a text: guessed, not printed
        (["--variant", "or-later", "--threshold", "1", "GPL-2.0-only"], True),
    ],
)
def test_a_variant_warning_is_for_a_printed_result(
    db: str, args: list[str], said: bool
) -> None:
    result = CliRunner().invoke(cli, ["--db", db, "detect", *args])
    lines = [x for x in result.stderr.splitlines() if "days old" not in x]
    assert bool(lines) is said


@pytest.mark.parametrize(
    "value",
    [
        "GPL2+",
        "GPL-2.0 only",
        "GPL-2.0 or later",
        "GPL-2.0+",
        "GPL-2.0",
        "MIT",
    ],
)
def test_one_value_is_exact_alike_in_every_channel(db: str, value: str) -> None:
    """``resolve()`` says whether a rewrite rule read the value; the argument,
    a tag (of its expression, not the words after it), a field and ``--id``
    all follow it."""
    detector = LicenseDetector(db)
    seen = {
        "argument": detector.detect(text=value),
        "tag": detector.detect(text=f"# SPDX-License-Identifier: {value}\n"),
        "field": detector.detect(text=f'{{"license": "{value}"}}'),
    }
    if " " not in value:
        seen["id"] = detector.detect(license_id=value)
    exact = {
        how: [(r["expression"], r["exact"]) for r in found[:1]]
        for how, found in seen.items()
        if found
    }
    assert len({tuple(v) for v in exact.values()}) == 1, exact


@pytest.mark.parametrize(
    ("variant", "tags", "expected", "said"),
    [
        ("or-later", ("GPL-2.0", "GPL-2.0-or-later"), ("GPL-2.0-or-later", True), 0),
        ("only", ("GPL-2.0", "GPL-2.0-only"), ("GPL-2.0-only", True), 0),
        ("only", ("GPL-2.0-only", "GPL-2.0"), ("GPL-2.0-only", True), 0),
        ("only", ("GPL-2.0", "GPL-2.0"), ("GPL-2.0-only", False), 1),
    ],
)
def test_two_tags_keep_the_one_that_states_the_variant(  # pylint: disable=R0913,R0917
    db: str,
    given: GivenWarnings,
    variant: Variant,
    tags: tuple[str, str],
    expected: tuple[str, bool],
    said: int,
) -> None:
    text = "".join(f"# SPDX-License-Identifier: {t}\n" for t in tags)
    (found,) = LicenseDetector(db).detect(text=text, variant=variant)
    assert (found["expression"], found["variant_stated"]) == expected
    assert len(given.take()) == said


def test_a_guess_is_said_for_the_printed_id_not_a_substring_of_it(
    given: GivenWarnings,
) -> None:
    """``gpl-2.0-only`` is inside ``lgpl-2.0-only``: only the printed one."""
    shown = _hit("LGPL-2.0-only", 1.0, "id")
    shown["evidence"] = Evidence(value="LGPL-2.0")
    hidden = _hit("GPL-2.0-only", 0.5, "id")  # below the bar: not printed

    def produce() -> list[RawMatch | InternalMatch]:
        warn_guess("LGPL-2.0", "LGPL-2.0-only")
        warn_guess("GPL-2.0", "GPL-2.0-only")
        return [shown, hidden]

    read_as("only", produce)
    assert [str(w) for w in given.take()] == [
        "input: variant not stated: LGPL-2.0; using LGPL-2.0-only"
    ]


def test_a_manifest_field_read_by_a_name_is_found_by_field(db: str) -> None:
    """A prose name is read by a rule, so not exact, yet still the field's."""
    (found,) = LicenseDetector(db).detect(text='{"license": "The MIT License"}')
    assert (found["expression"], found["method"], found["exact"]) == (
        "MIT",
        "field",
        False,
    )


def test_an_empty_variant_is_a_usage_error_with_its_own_condition(db: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db, "detect", "--variant", "", "MIT"])
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith("ERROR: option: empty: --variant; use one of")


def test_a_tag_with_only_before_an_operator_is_refused(db: str) -> None:
    """It would answer ``GPL-2.0-only`` and drop MIT, which the argument and a
    field refuse too (as after a grant): no answer, whatever the variant."""
    text = "# SPDX-License-Identifier: GPL-2.0 only OR MIT\n"
    for variant in ("auto", "only", "or-later"):
        assert not LicenseDetector(db).detect(text=text, variant=variant)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("GPL2+", ("GPL-2.0-or-later", False)),  # the expression is re-spelt
        ("MIT;", ("MIT", True)),  # the words after it are not judged
        ("MIT License", ("MIT", True)),
    ],
)
@pytest.mark.parametrize(
    "line",
    [
        "// SPDX-License-Identifier: {}",
        "/* SPDX-License-Identifier: {} */",
        "<!-- SPDX-License-Identifier: {} -->",
        "SPDX-License-Identifier: {} SPDX-FileCopyrightText: 2020 x",
    ],
)
def test_what_follows_a_tag_on_its_line_does_not_change_its_exactness(
    db: str, line: str, tag: str, expected: tuple[str, bool]
) -> None:
    found = LicenseDetector(db).detect(text=line.format(tag) + "\n")
    assert [(r["expression"], r["exact"]) for r in found[:1]] == [expected]


def test_as_written_keeps_the_exact_name_of_a_deprecated_id(db: str) -> None:
    found = LicenseDetector(db).detect(
        text="GNU General Public License v2.0", variant="as-written"
    )
    assert [(r["expression"], r["exact"]) for r in found[:1]] == [("GPL-2.0", True)]
