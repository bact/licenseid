# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden detect() answers moved by the notice-free head query of Tier 1
(``retrieval._notice_free_candidates``), for harness_changes.DETECT_CHANGES:
{case: (new value, reason)}. Each is a slice of a licence text with a
copyright notice in its first 20 words; none of them answered its own
licence before, and none does now: another near neighbour ranks first."""

# pylint: disable=line-too-long

_NOTICE = (
    "the copyright notice no longer fills the first 20 words of the Tier 1"
    " query: a near neighbour joins the candidates and ranks above the old"
    " wrong answer (neither is the licence of the slice)"
)

NOTICE_QUERY_CHANGES: dict[str, tuple[str, str]] = {
    "short/Buddy/head_800": (
        "MIT-Modern-Variant\ttext\tno\t0.7130",
        _NOTICE,
    ),
    "short/Game-Programming-Gems/head_900": (
        "softSurfer\ttext\tno\t0.6114",
        _NOTICE,
    ),
    "short/HPND-Pbmplus/head_1000": (
        "HPND-Netrek\ttext\tno\t0.8557",
        _NOTICE,
    ),
    "short/HPND-UC-export-US/head_1500": (
        "HPND-Netrek\ttext\tno\t0.8100",
        _NOTICE,
    ),
    "short/HPND-UC/tail_1500": (
        "HPND-Netrek\ttext\tno\t0.8423",
        _NOTICE,
    ),
    "short/HPND-merchantability-variant/head_700": (
        "ISC-Veillard\ttext\tno\t0.7740",
        _NOTICE,
    ),
    "short/HPND-sell-regexpr/head_800": (
        "HPND-sell-variant-MIT-disclaimer-rev\ttext\tno\t0.7828",
        _NOTICE,
    ),
    "short/HPND-sell-variant-MIT-disclaimer/head_900": (
        "HPND-sell-variant-MIT-disclaimer-rev\ttext\tno\t1.0000",
        _NOTICE,
    ),
    "short/ISO-permission/head_900": (
        "OAR\ttext\tno\t0.5806",
        _NOTICE,
    ),
    "short/Kastrup/head_800": (
        "URT-RLE\ttext\tno\t0.5887",
        _NOTICE,
    ),
    "short/Newsletr/tail_1000": (
        "Zlib\ttext\tno\t0.7114",
        _NOTICE,
    ),
    "short/SGI-OpenGL/head_800": (
        "HPND-export2-US\ttext\tno\t0.8670",
        _NOTICE,
    ),
    "short/Spencer-99/head_700": (
        "xlock\ttext\tno\t0.6356",
        _NOTICE,
    ),
    "short/TCP-wrappers/head_1500": (
        "BSD-4.3TAHOE\ttext\tno\t0.6851",
        _NOTICE,
    ),
    "short/TU-Berlin-1.0/tail_700": (
        "Zlib\ttext\tno\t0.5999",
        _NOTICE,
    ),
    "short/Xerox/head_2000": (
        "OFFIS\ttext\tno\t0.6789",
        _NOTICE,
    ),
    "short/generic-xts/head_2000": (
        "dtoa\ttext\tno\t0.8472",
        _NOTICE,
    ),
    "short/lsof/head_1000": (
        "Spencer-94\ttext\tno\t0.8836",
        _NOTICE,
    ),
    "short/pnmstitch/head_700": (
        "BSD-2-Clause-Views\ttext\tno\t0.7890",
        _NOTICE,
    ),
    "short/psutils/head_800": (
        "MulanPSL-1.0\ttext\tno\t0.4264",
        _NOTICE,
    ),
    "mixed/mixed-content/CC-BY-NC-SA-2.0-UK/lib_mock_cc-by-nc-sa-2.0-uk_1.py": (
        "Parity-7.0.0\ttext\tno\t0.4889",
        _NOTICE,
    ),
    "mixed/mixed-content/GFDL-1.1-no-invariants-or-later/lib_mock_gfdl-1.1-no-invariants-or-later_1.py": (
        "GPL-3.0-only\ttext\tno\t0.4708",
        _NOTICE,
    ),
    "mixed/mixed-content/Mackerras-3-Clause-acknowledgment/lib_mock_mackerras-3-clause-acknowledgment_1.py": (
        "GFDL-1.1-invariants-only\ttext\tno\t0.4696",
        _NOTICE,
    ),
}
