# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and a ``/`` between licence IDs (roadmap item 43): read as
``OR`` when the value is IDs spelt as listed, and nothing else; every other
value answers as it did on 0.8.3 (``slash_pins``)."""
# pylint: disable=missing-function-docstring

from typing import Any

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from slash_pins import PINS
from slash_values import ACCEPTED, REFUSED

from licenseid import LicenseDatabase, resolve, resolveslash
from licenseid.resolvecompound import Compound
from licenseid.resolvecompound import read_compound as real_compound
from licenseid.resolveleaf import Found
from licenseid.resolver import MAX_EXPRESSION_CHARS
from licenseid.resolvertypes import CATEGORY_ORDER
from licenseid.resolveslash import slash_parts


def weakest(*categories: str) -> str:
    return max(categories, key=CATEGORY_ORDER.index)


def pin_of(result: Any) -> dict[str, Any]:
    """The fields of ``slash_pins``."""
    return {
        "expression": result["expression"],
        "category": result["category"],
        "reason": result["reason"],
        "steps": [(s["kind"], s["detail"]) for s in result["steps"]],
        "operands": [
            (o["text"], tuple(o["span"]), o["expression"], o["reason"])
            for o in result["operands"]
        ],
    }


@pytest.mark.parametrize(("value", "expression", "operands"), ACCEPTED)
def test_ids_joined_by_a_slash_read_as_or(
    corpus_db: LicenseDatabase,
    value: str,
    expression: str,
    operands: list[tuple[str, tuple[int, int]]],
) -> None:
    result = resolve(value, corpus_db)
    assert result["expression"] == expression
    assert result["reason"] is None
    kinds = [s["kind"] for s in result["steps"]]
    assert "separator" in kinds
    slash = [s for s in result["steps"] if s["detail"] == "slash as OR"]
    assert len(slash) == 1
    assert slash[0]["to"] == " OR ".join(text for text, _ in operands)
    assert [(o["text"], tuple(o["span"])) for o in result["operands"]] == operands
    for operand in result["operands"]:
        assert value[operand["span"][0] : operand["span"][1]] == operand["text"]
    # The weakest of the compound's own category and ``separator``.
    alone = resolve(expression, corpus_db)["category"]
    assert result["category"] == weakest("separator", alone)


@pytest.mark.parametrize("value", [a[0] for a in ACCEPTED])
def test_a_read_slash_value_is_a_fixed_point(
    corpus_db: LicenseDatabase, value: str
) -> None:
    expression = resolve(value, corpus_db)["expression"]
    assert expression is not None
    assert resolve(expression, corpus_db)["expression"] == expression


def test_the_positive_controls_of_crates_io(corpus_db: LicenseDatabase) -> None:
    # winapi, filetime_creation, tokio-icmp-echo and sourcefile
    for value in ("MIT/Apache-2.0", "Apache-2.0/MIT"):
        assert resolve(value, corpus_db)["expression"] == "Apache-2.0 OR MIT"


def test_the_negative_control_non_standard_stays_refused(
    corpus_db: LicenseDatabase,
) -> None:
    result = resolve("non-standard", corpus_db)  # ring: no slash, item 49
    assert result["expression"] is None
    assert result["category"] == "unresolved"


@pytest.mark.parametrize("value", REFUSED, ids=[repr(v)[:40] for v in REFUSED])
def test_every_other_value_answers_as_on_0_8_3(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert pin_of(resolve(value, corpus_db)) == PINS[value]


def test_every_pinned_value_is_in_the_table() -> None:
    assert set(PINS) == set(REFUSED)


def test_the_gate_reads_none_of_them(corpus_db: LicenseDatabase) -> None:
    """The gate itself, not the readers behind it: a value in the table is
    no list of IDs, whatever ``read_compound`` would do with it."""
    for value in REFUSED:
        assert slash_parts(value, corpus_db) is None, value


def test_the_gate_reads_the_accepted_ones(corpus_db: LicenseDatabase) -> None:
    for value, _, operands in ACCEPTED:
        if value.strip(' \t"()').endswith("."):  # an end mark, read later
            continue
        inner = value.strip(' \t"()')
        parts = slash_parts(inner, corpus_db)
        assert parts is not None, value
        assert [part.text for part in parts] == [text for text, _ in operands]


def test_the_gate_asks_whether_the_value_is_a_url(
    corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ID pair is a URL on the List today; the check is kept for one."""
    assert slash_parts("MIT/ISC", corpus_db) is not None
    monkeypatch.setattr(resolveslash, "is_url", lambda text: True)
    assert slash_parts("MIT/ISC", corpus_db) is None


def test_a_compound_that_gives_no_expression_leaves_the_value_as_it_was(
    corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal is the one `main` gives, not the compound's."""

    def refuse(_db: object, _text: str, _start: int, found: Found) -> Compound:
        found.category, found.reason = "unresolved", "operand not resolved: x"
        return Compound([], True, True)

    monkeypatch.setattr(resolveslash, "read_compound", refuse)
    found = Found()
    assert resolveslash.read_slash_list(corpus_db, "MIT/ISC", 0, found) is None
    assert found == Found()
    assert resolve("MIT/ISC", corpus_db)["reason"] == "not an SPDX operator: /"


def test_a_refused_pair_is_refused_wherever_it_stands(
    corpus_db: LicenseDatabase,
) -> None:
    for value in ("MIT/X11/ISC", "ISC/X11/MIT", "X11+/MIT", "Zlib/ISC/Libpng"):
        assert slash_parts(value, corpus_db) is None, value
    assert slash_parts("MIT/ISC", corpus_db) is not None


def test_the_length_limit_is_the_resolvers() -> None:
    assert resolveslash.MAX_JOINED == MAX_EXPRESSION_CHARS


def test_a_value_over_the_limit_once_joined_is_refused(
    corpus_db: LicenseDatabase,
) -> None:
    ids = ["Apache-2.0"] * 149
    value = "/".join(ids)
    assert len(value) < 2000 < len(" OR ".join(ids))
    assert resolve(value, corpus_db)["expression"] is None


@pytest.mark.parametrize("wrong", ["count", "text"])
def test_a_compound_that_reads_other_operands_is_not_taken(
    corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch, wrong: str
) -> None:
    def other(db: Any, text: str, start: int, found: Found) -> Compound:
        compound = real_compound(db, text, start, found)
        if wrong == "count":
            return compound._replace(operands=compound.operands[:1])
        compound.operands[0]["text"] = "x"
        return compound

    monkeypatch.setattr(resolveslash, "read_compound", other)
    found = Found()
    assert resolveslash.read_slash_list(corpus_db, "MIT/ISC", 0, found) is None
    assert found == Found()
