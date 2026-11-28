# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden detect() answers moved when Tier 2 aligned a fragment's
characters on the region of a text its word codes locate
(``licenseid.wordregion``, ``licenseid.regionalign``) instead of the whole
text (0.10.0, task T4), for harness_changes.DETECT_CHANGES: {case: (new
value, reason)}.

A region never aligns higher than the whole text, but where several windows
tie, the one ``token_sort_ratio`` scores again can differ, and so can the
score. Judged at 0.85 against the licence a slice was cut from. ``long``,
``mixed``, ``id``, ``name``, ``value`` and ``cli`` do not move."""

_SAME = (
    "the same answer, another score: the window found on the word region is"
    " not the whole text's, and scores otherwise by sorted words"
)
_UNDER = (
    "no answer before or after: a row under 0.85 scored on the window of the"
    " word region"
)
_WRONG_GONE = (
    "a wrong answer gone: the window of the word region puts the other"
    " licence under 0.85"
)
_FINDING = (
    "FINDING, a new wrong answer: the 2-Clause text lacks the 3-Clause's"
    " endorsement clause; the whole text's best window is trimmed at its"
    " start, the region leaves the start out, and its window scores higher"
    " by sorted words (working-docs/implementation/word-region.md, section 6)"
)

REGION_CHANGES: dict[str, tuple[str, str]] = {
    "short/Boehm-GC-without-fee/tail_300": (
        "Boehm-GC\ttext\tno\t0.9652",
        _SAME,
    ),
    "short/Brian-Gladman-2-Clause/head_700": (
        "Brian-Gladman-3-Clause-no-conversion\ttext\tno\t0.8616",
        _FINDING,
    ),
    "short/CFITSIO/head_700": (
        "NIST-PD-fallback\ttext\tno\t0.8236",
        _UNDER,
    ),
    "short/HPND-Pbmplus/head_1000": (
        "HPND-Netrek\ttext\tno\t0.8250",
        _WRONG_GONE,
    ),
    "short/HPND-sell-variant/head_1000": (
        "HPND-sell-variant-critical-systems\ttext\tno\t0.9096",
        _SAME,
    ),
    "short/Latex2e/head_2000": (
        "Latex2e-translated-notice\ttext\tno\t0.9238",
        _SAME,
    ),
    "short/Linux-OpenIB/head_700": (
        "NCL\ttext\tno\t0.8439",
        _UNDER,
    ),
    "short/NCGL-UK-2.0/tail_700": (
        "OGL-UK-3.0\ttext\tno\t0.7552",
        _UNDER,
    ),
    "short/NICTA-1.0/tail_900": (
        "CC-BY-2.5-AU\ttext\tno\t0.8100",
        _UNDER,
    ),
    "short/SNIA/tail_300": (
        "NOSL\ttext\tno\t0.6915",
        _UNDER,
    ),
    "short/pnmstitch/head_700": (
        "BSD-1-Clause\ttext\tno\t0.9067",
        _SAME,
    ),
    "several/mpl-header-notice": (
        "MPL-2.0-no-copyleft-exception\ttext\tno\t0.7418",
        _UNDER,
    ),
}
