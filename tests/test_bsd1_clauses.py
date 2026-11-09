# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""`licenseid.bsdclauses.bsd_clause_id`: the numbered conditions of a text
name its BSD-N-Clause. The marker built on it is in `test_bsd1_marker`."""
# pylint: disable=missing-function-docstring

import time

import pytest
from timing import slack

from licenseid.bsdclauses import bsd_clause_id

SOURCE = (
    "1. Redistributions of source code must retain the above copyright"
    " notice, this list of conditions and the following disclaimer.\n\n"
)
BINARY = (
    "2. Redistributions in binary form must reproduce the above copyright notice.\n\n"
)
ENDORSE = (
    "3. Neither the name of the copyright holder nor the names of its"
    " contributors may be used to endorse or promote products.\n\n"
)
ADVERTISING = (
    "3. All advertising materials mentioning features or use of this"
    " software must display the following acknowledgement.\n\n"
)
ENDORSE_4 = ENDORSE.replace("3.", "4.")
DISCLAIMER = (
    "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS"
    ' "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED.\n'
)
PREAMBLE = (
    "Copyright (c) 2024 Jane Doe. All rights reserved.\n\n"
    "Redistribution and use in source and binary forms, with or without"
    " modification, are permitted provided that the following conditions"
    " are met:\n\n"
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (SOURCE + BINARY, "BSD-2-Clause"),
        (SOURCE + BINARY + ENDORSE, "BSD-3-Clause"),
        (SOURCE + BINARY + ADVERTISING + ENDORSE_4, "BSD-4-Clause"),
        # The highest number counts, not how many conditions there are.
        (SOURCE + ENDORSE, "BSD-3-Clause"),
        # Indented, as in a comment block.
        ("   " + SOURCE + "\t" + BINARY, "BSD-2-Clause"),
        # Case does not matter.
        (SOURCE.upper() + BINARY.upper(), "BSD-2-Clause"),
        # Five conditions are no BSD-N-Clause.
        (
            SOURCE + BINARY + ENDORSE + "4. The name may not be used.\n5. The"
            " author is not liable.\n\n",
            None,
        ),
        ("", None),
        ("Redistribution and use are permitted.\n", None),
        # A number not at the start of a line is no numbered condition.
        ("See section 2. Redistribution is permitted.\n", None),
    ],
)
def test_bsd_clause_id(body: str, expected: str | None) -> None:
    assert bsd_clause_id(PREAMBLE + body + DISCLAIMER) == expected


@pytest.mark.parametrize(
    "line_break",
    ["\n", "\r\n", "\r", " \n"],
    ids=["LF", "CRLF", "CR", "space LF"],
)
def test_a_run_of_blank_lines_is_read_in_linear_time(line_break: str) -> None:
    # 20,000 blank lines took 3 s (6 s with CRLF) when the indent was `\s*`.
    payload = SOURCE + line_break * 20_000 + "x"
    start = time.monotonic()
    assert bsd_clause_id(payload) is None
    elapsed = time.monotonic() - start
    assert elapsed < slack(0.5), f"took {elapsed:.3f}s"


# BSD-1-Clause: condition 1 alone, followed by the disclaimer.
ONE_CLAUSE = {
    "as written": SOURCE + DISCLAIMER,
    "indented": "  " + SOURCE + DISCLAIMER,
    "lower case": SOURCE.lower() + DISCLAIMER.lower(),
    "singular": SOURCE.replace("Redistributions", "Redistribution") + DISCLAIMER,
    "CRLF": (SOURCE + DISCLAIMER).replace("\n", "\r\n"),
    "wrapped": SOURCE.replace(" of source", "\nof\n   source") + DISCLAIMER,
}


@pytest.mark.parametrize("body", ONE_CLAUSE.values(), ids=ONE_CLAUSE.keys())
def test_condition_1_alone_with_the_disclaimer_is_bsd_1(body: str) -> None:
    assert bsd_clause_id(PREAMBLE + body) == "BSD-1-Clause"


# Condition 1 alone, but not the whole of BSD-1-Clause: a truncated BSD-2, 3
# or 4 text, or another condition 1.
NOT_ONE_CLAUSE = {
    "no disclaimer": SOURCE,
    "disclaimer first": DISCLAIMER + "\n" + SOURCE,
    "binary form unnumbered": SOURCE + BINARY[3:] + DISCLAIMER,
    "endorse unnumbered": SOURCE + ENDORSE[3:] + DISCLAIMER,
    "advertising unnumbered": SOURCE + ADVERTISING[3:] + DISCLAIMER,
    "binary form after the disclaimer": SOURCE + DISCLAIMER + BINARY[3:],
    "other condition 1": SOURCE.replace("source code", "documentation") + DISCLAIMER,
    "may retain": SOURCE.replace("must retain", "may retain") + DISCLAIMER,
    "retaining": SOURCE.replace("must retain", "must retainer") + DISCLAIMER,
    "not at a line start": "1. The author is not responsible.\n\nSee 1."
    " Redistributions of source code must retain the notice.\n" + DISCLAIMER,
    "numbered 0": "0. Redistributions of source code must retain the"
    " notice.\n1. The author is not responsible.\n" + DISCLAIMER,
    "other disclaimer": SOURCE + "THE SOFTWARE IS PROVIDED AS IS.\n",
    "condition 2 too": SOURCE + BINARY.replace("binary form", "any form") + DISCLAIMER,
}


@pytest.mark.parametrize("body", NOT_ONE_CLAUSE.values(), ids=NOT_ONE_CLAUSE.keys())
def test_condition_1_alone_without_the_rest_is_not_bsd_1(body: str) -> None:
    assert bsd_clause_id(PREAMBLE + body) != "BSD-1-Clause"
