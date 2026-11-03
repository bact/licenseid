# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The invariants of the pre-release harness, each a function that returns
why a value breaks it, or ``None``; the tests loop over a value set and
report every breaker. The value set is the resolver corpus (parity corpus and
PyPI sample) and the output of ``harness_gen.generate``."""

import json
from collections.abc import Callable, Iterable
from typing import Any

import rfc8785
from resolver_corpus import corpus_rows

from licenseid import InvalidInputError, resolve
from licenseid.detector import LicenseDetector
from licenseid.result import json_line, read_text_field, resolution_lines, text_line
from licenseid.types import Detection
from tools.pypi_licence_sample.answer import unescape_field

#: The seed of the every-commit run; the benchmark run uses the same stream,
#: longer, so a failure it finds is found again by the short one if it is early.
SEED = 20260
NUMERIC = {"SCORE", "SIMILARITY", "COVERAGE"}


def corpus_values() -> list[str]:
    """Every value of the parity corpus and the PyPI sample."""
    return [unescape_field(row["value"]) for row in corpus_rows()]


def failures(values: Iterable[str], check: Callable[[str], str | None]) -> list[str]:
    """``value -> why`` lines of the values that break *check*, at most 10
    (the first), with the total."""
    broken = []
    for value in values:
        why = check(value)
        if why:
            broken.append(f"{value!r}: {why}")
    return [*broken[:10], f"({len(broken)} in all)"] if broken else []


def never_raises_match(value: str) -> str | None:
    """``resolve()`` returns for any str, or raises InvalidInputError."""
    try:
        resolve(value, source="packaged")
    except InvalidInputError:
        return None
    except Exception as error:  # pylint: disable=broad-exception-caught
        return f"resolve raised {type(error).__name__}: {str(error)[:80]}"
    return None


def detect_all(
    detector: LicenseDetector, values: Iterable[str]
) -> dict[str, list[Detection] | Exception]:
    """``detect(text=...)`` of each value once: its results, or the error it
    raised (an InvalidInputError is no failure: the value is left out)."""
    outcomes: dict[str, list[Detection] | Exception] = {}
    for value in values:
        try:
            outcomes[value] = detector.detect(text=value)
        except InvalidInputError:
            continue
        except Exception as error:  # pylint: disable=broad-exception-caught
            outcomes[value] = error
    return outcomes


def detect_never_raises(outcome: list[Detection] | Exception) -> str | None:
    """*outcome* of :func:`detect_all` is a result list, not an error."""
    if isinstance(outcome, Exception):
        return f"detect raised {type(outcome).__name__}: {str(outcome)[:80]}"
    return None


def as_text(value: object) -> str:
    """A JSON value as the text line writes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def text_fields(line: str) -> dict[str, str]:
    """A text line's fields, each value read back."""
    pairs = [field.partition("=") for field in line.split("\t")]
    return {key: read_text_field(value) for key, _, value in pairs}


def line_matches_json(line: str, record: dict[str, object]) -> str | None:
    """Every field of the text *line* equals the same key of *record* (lower
    case), a score within the four places the text keeps."""
    for key, text in text_fields(line).items():
        if key.lower() not in record:
            return f"{key} is not in the JSON"
        value = record[key.lower()]
        if (
            key in NUMERIC
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and text
        ):
            if abs(float(text) - value) > 5e-5:
                return f"{key}: text {text!r}, JSON {value!r}"
        elif text != as_text(value):
            return f"{key}: text {text!r}, JSON {value!r}"
    return None


def match_lines_agree(lines: list[str], record: dict[str, Any]) -> str | None:
    """The lines ``licenseid resolve`` prints read back to the JSON *record*:
    the head, each applied step (steps, then qualifiers), the reason and the
    operands. The expected lines are built from the record, not from
    ``resolution_lines``."""
    why = line_matches_json(lines[0], record)
    if why:
        return why
    fields = [text_fields(line) for line in lines[1:]]
    applied = [s for s in (*record["steps"], *record["expansions"]) if s["applied"]]
    steps = [(f["STEP"], f["FROM"], f["TO"]) for f in fields if "STEP" in f]
    if steps != [
        (s["kind"], *(as_text(s[k]) for k in ("from", "to"))) for s in applied
    ]:
        return f"STEP lines {steps!r} differ from the steps"
    reasons = [f["REASON"] for f in fields if "REASON" in f]
    if reasons != ([] if record["reason"] is None else [record["reason"]]):
        return f"REASON lines {reasons!r}, JSON {record['reason']!r}"
    operands = [
        (f["OPERAND"], f["EXPRESSION"], f["CATEGORY"]) for f in fields if "OPERAND" in f
    ]
    if operands and operands != [
        (o["text"], as_text(o["expression"]), o["category"]) for o in record["operands"]
    ]:
        return f"OPERAND lines {operands!r} differ from the operands"
    return None


def canonical(line: str) -> str | None:
    """*line* is the RFC 8785 form of the object it holds."""
    if rfc8785.dumps(json.loads(line)) != line.encode("utf-8"):
        return "JSON is not canonical"
    return None


def match_output_agrees(value: str) -> str | None:
    """The text line, the JSON line and the canonical form of a ``resolve()``
    result agree."""
    try:
        found = resolve(value, source="packaged")
    except InvalidInputError:
        return None
    line = json_line(found)
    return canonical(line) or match_lines_agree(
        resolution_lines(found), json.loads(line)
    )


def detection_output_agrees(result: Detection) -> str | None:
    """The same for one ``detect()`` result."""
    line = json_line(result)
    return canonical(line) or line_matches_json(text_line(result), json.loads(line))


def detect_output_agrees(outcome: list[Detection] | Exception) -> str | None:
    """:func:`detection_output_agrees` on every result of *outcome*."""
    if isinstance(outcome, Exception):
        return None  # detect_never_raises names it
    for result in outcome:
        why = detection_output_agrees(result)
        if why:
            return why
    return None


def answer_is_stable(value: str) -> str | None:
    """Reading an answer again gives the answer."""
    try:
        first = resolve(value, source="packaged")
    except InvalidInputError:
        return None
    expression = first["expression"]
    if expression is None:
        return None
    again = resolve(expression, source="packaged")["expression"]
    return None if again == expression else f"{expression!r} read again: {again!r}"
