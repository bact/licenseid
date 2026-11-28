# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden detect() answers moved when Tier 1 took its candidates from the
word 3-grams of the stored postings (``licenseid.gramselect``) instead of the
FTS5 query, and the windowed search of mixed content went (0.10.0, task T3),
for harness_changes.DETECT_CHANGES: {case: (new value, reason)}.

Judged at 0.85 against the licence a slice was cut from (the ``short`` part's
database holds the long-text fixtures only: a slice's own licence may have no
text in it). ``long``, ``id`` and ``cli`` do not move."""

# pylint: disable=line-too-long

_ROW = (
    "no answer before or after: a row under 0.85 from the gram selection (the"
    " top 3 by gram score and those within 0.05 of the best, at most 20)"
)
_NO_ROW = (
    "no answer before or after: no List text shares enough word grams (best"
    " under 0.1), and the windowed search that listed a weak row is gone"
)
_RIGHT = (
    "the slice's own licence, now held whole: the word grams fetch its text,"
    " which the FTS5 query missed"
)
_HELD = (
    "the slice is held whole in the SWL text (TCL has no text in this"
    " database): an answer the golden gate allows"
)
_TIE = (
    "another licence that holds the slice whole, at 1.0 as before (OLDAP-2.2.1"
    " has no text in this database): a tie of two others, ranked by ID"
)
_OTHER = (
    "one wrong answer for another (the slice's licence has no text in this database)"
)
_WRONG_GONE = "a wrong answer gone: the row of another licence is under 0.85"
_KEPT = (
    "as under the notice-free head query of 0.9.2, now removed: the word grams"
    " of the whole slice reach past its copyright notice too, and the same"
    " near neighbour ranks first (neither is the licence of the slice)"
)
_EXAMINE = (
    "FINDING: a new answer that is not the slice's licence, which has no text"
    " in this database; the plan examines it in T4 and T5 (section 3.6)"
)

GRAM_CHANGES: dict[str, tuple[str, str]] = {
    "mixed/mixed-content-curated/GPL-2.0-or-later/CITATION.cff": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content-curated/MPL-2.0/libreoffice.txt": (
        "RPSL-1.0\ttext\tno\t0.6000",
        _ROW,
    ),
    "mixed/mixed-content/AFL-1.2/lib_mock_afl-1.2_3.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/AFL-2.1/README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/AGPL-1.0-only/lib_mock_agpl-1.0-only_3.py": (
        "AGPL-3.0-only\ttext\tno\t0.6979",
        _ROW,
    ),
    "mixed/mixed-content/AGPL-3.0-or-later/1_README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/Apache-1.1/README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/BSD-2-Clause-Darwin/README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/BSD-3-Clause/3_README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/Bitstream-Charter/README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CC-BY-3.0-US/README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CC-BY-NC-SA-2.0-DE/README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CC-BY-NC-SA-2.0-UK/index.html": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CC-BY-NC-SA-2.0-UK/lib_mock_cc-by-nc-sa-2.0-uk_1.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CDDL-1.0/lib_mock_cddl-1.0_0.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CDDL-1.0/lib_mock_cddl-1.0_2.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CERN-OHL-1.2/2_README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CERN-OHL-1.2/index.html": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/CERN-OHL-W-2.0/index.html": (
        "Parity-7.0.0\ttext\tno\t0.4940",
        _ROW,
    ),
    "mixed/mixed-content/EPICS/pubspec.yaml": (
        "BlueOak-1.0.0\ttext\tno\t0.5647",
        _ROW,
    ),
    "mixed/mixed-content/EUPL-1.2/2_README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/GFDL-1.1-no-invariants-or-later/index.html": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/GFDL-1.1-no-invariants-or-later/lib_mock_gfdl-1.1-no-invariants-or-later_1.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/GPL-2.0-only/lib_mock_gpl-2.0-only_3.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/GPL-2.0-or-later/3_README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/ImageMagick/index.html": (
        "Parity-7.0.0\ttext\tno\t0.4780",
        _ROW,
    ),
    "mixed/mixed-content/Interbase-1.0/lib_mock_interbase-1.0_1.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/LGPL-2.0-or-later/lib_mock_lgpl-2.0-or-later_0.py": (
        "BUSL-1.1\ttext\tno\t0.4737",
        _ROW,
    ),
    "mixed/mixed-content/MIT-STK/lib_mock_mit-stk_0.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/MPL-1.1/pubspec.yaml": (
        "BlueOak-1.0.0\ttext\tno\t0.5057",
        _ROW,
    ),
    "mixed/mixed-content/MPL-2.0-no-copyleft-exception/index.html": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/MPL-2.0-no-copyleft-exception/lib_mock_mpl-2.0-no-copyleft-exception_0.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/MS-PL/lib_mock_ms-pl_0.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/Mackerras-3-Clause-acknowledgment/lib_mock_mackerras-3-clause-acknowledgment_1.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/OFL-1.0-no-RFN/lib_mock_ofl-1.0-no-rfn_1.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/OFL-1.1-no-RFN/1_README.md": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/OFL-1.1-no-RFN/lib_mock_ofl-1.1-no-rfn_2.py": (
        "OFL-1.0\ttext\tno\t0.4753",
        _ROW,
    ),
    "mixed/mixed-content/W3C-19980720/lib_mock_w3c-19980720_0.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "mixed/mixed-content/libpng-1.6.35/lib_mock_libpng-1.6.35_2.py": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "name/CC-BY-NC-SA-2.0-DE/name_distored": (
        "EUPL-1.2\ttext\tno\t0.6619",
        _ROW,
    ),
    "several/mpl-header-notice": (
        "MPL-2.0-no-copyleft-exception\ttext\tno\t0.7409",
        _ROW,
    ),
    "short/AMD-newlib/head_2000": (
        "pkgconf\ttext\tno\t0.6674",
        _ROW,
    ),
    "short/AMDPLPA/tail_2000": (
        "SGI-B-1.0\ttext\tno\t0.5117",
        _ROW,
    ),
    "short/Abstyles/tail_1500": (
        "Linux-man-pages-copyleft-2-para\ttext\tno\t0.7411",
        _ROW,
    ),
    "short/Adobe-Glyph/tail_300": (
        "APSL-1.0\ttext\tno\t0.6747",
        _ROW,
    ),
    "short/Afmparse/head_700": (
        "HPND-DEC\ttext\tno\t0.5362",
        _ROW,
    ),
    "short/Apache-1.1/tail_800": (
        "Apache-1.1\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/BSD-Protection/tail_300": (
        "BSD-Protection\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/Bahyph/tail_900": (
        "Zlib\ttext\tno\t0.6026",
        _ROW,
    ),
    "short/Barr/head_1000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/Beerware/tail_1000": (
        "AGPL-3.0-only\ttext\tno\t0.4821",
        _ROW,
    ),
    "short/Borceux/tail_500": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/Buddy/head_800": (
        "SWL\ttext\tno\t0.7419",
        _ROW,
    ),
    "short/CECILL-1.0/tail_900": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/CMU-Mach/head_800": (
        "CMU-Mach-nodoc\ttext\tno\t0.7734",
        _ROW,
    ),
    "short/Clips/tail_500": (
        "NetCDF\ttext\tno\t0.8742",
        _EXAMINE,
    ),
    "short/Community-Spec-1.0/head_700": (
        "CPOL-1.02\ttext\tno\t0.5531",
        _ROW,
    ),
    "short/Cronyx/tail_800": (
        "xkeyboard-config-Zinoviev\ttext\tno\t0.7091",
        _ROW,
    ),
    "short/CrystalStacker/head_1000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/D-FSL-1.0/head_1500": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/DocBook-XML/tail_800": (
        "MIT-advertising\ttext\tno\t0.7683",
        _ROW,
    ),
    "short/GLWTPL/tail_300": (
        "Imlib2\ttext\tno\t0.8838",
        _OTHER,
    ),
    "short/Glulxe/tail_1000": (
        "GFDL-1.1-invariants-only\ttext\tno\t0.5149",
        _ROW,
    ),
    "short/Graphics-Gems/head_1500": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/HPND-INRIA-IMAG/head_700": (
        "HPND-MIT-disclaimer\ttext\tno\t0.8390",
        _ROW,
    ),
    "short/HPND-Intel/tail_700": (
        "NIST-PD-fallback\ttext\tno\t0.5623",
        _ROW,
    ),
    "short/HPND-Pbmplus/head_1000": (
        "HPND-Netrek\ttext\tno\t0.8557",
        _KEPT,
    ),
    "short/HPND-UC-export-US/head_1500": (
        "HPND-export-US\ttext\tno\t0.6723",
        _ROW,
    ),
    "short/HPND-UC/tail_1500": (
        "HPND-Netrek\ttext\tno\t0.8423",
        _KEPT,
    ),
    "short/HPND-export-US-modify/tail_300": (
        "HPND-Netrek\ttext\tno\t0.7132",
        _ROW,
    ),
    "short/HPND-merchantability-variant/head_700": (
        "HP-1989\ttext\tno\t0.7508",
        _ROW,
    ),
    "short/HPND-sell-regexpr/head_800": (
        "HPND-sell-variant-MIT-disclaimer-rev\ttext\tno\t0.7828",
        _KEPT,
    ),
    "short/HPND-sell-variant-MIT-disclaimer/head_900": (
        "HPND-sell-variant-MIT-disclaimer-rev\ttext\tno\t1.0000",
        _KEPT,
    ),
    "short/IEC-Code-Components-EULA/tail_300": (
        "IEC-Code-Components-EULA\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/ISO-permission/head_900": (
        "OAR\ttext\tno\t0.5806",
        _KEPT,
    ),
    "short/Intel-ACPI/head_2000": (
        "CPAL-1.0\ttext\tno\t0.5183",
        _ROW,
    ),
    "short/JPL-image/tail_300": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/JasPer-2.0/tail_700": (
        "Widget-Workshop\ttext\tno\t0.7831",
        _ROW,
    ),
    "short/Kastrup/head_800": (
        "TermReadKey\ttext\tno\t0.5569",
        _ROW,
    ),
    "short/LPD-document/tail_500": (
        "Linux-man-pages-copyleft-2-para\ttext\tno\t0.6121",
        _ROW,
    ),
    "short/Linux-OpenIB/head_700": (
        "NCL\ttext\tno\t0.8430",
        _WRONG_GONE,
    ),
    "short/Lucida-Bitmap-Fonts/tail_900": (
        "HPND-sell-variant-critical-systems\ttext\tno\t0.7710",
        _ROW,
    ),
    "short/MIPS/head_1000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/MakeIndex/tail_800": (
        "Leptonica\ttext\tno\t0.6272",
        _ROW,
    ),
    "short/McPhee-slideshow/tail_900": (
        "SchemeReport\ttext\tno\t0.6510",
        _ROW,
    ),
    "short/NAIST-2003/tail_300": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/NCBI-PD/head_700": (
        "OSET-PL-2.1\ttext\tno\t0.4869",
        _ROW,
    ),
    "short/NCGL-UK-2.0/tail_700": (
        "OGL-UK-3.0\ttext\tno\t0.7587",
        _ROW,
    ),
    "short/NICTA-1.0/tail_900": (
        "CC-BY-3.0-AU\ttext\tno\t0.8121",
        _ROW,
    ),
    "short/NLOD-1.0/head_2000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/NLOD-2.0/tail_2000": (
        "BitTorrent-1.1\ttext\tno\t0.5008",
        _ROW,
    ),
    "short/Newsletr/tail_1000": (
        "CryptoSwift\ttext\tno\t0.6974",
        _ROW,
    ),
    "short/OCCT-PL/head_300": (
        "RPL-1.1\ttext\tno\t0.5507",
        _ROW,
    ),
    "short/OLDAP-2.2.1/tail_900": (
        "OLDAP-2.2\ttext\tno\t1.0000",
        _TIE,
    ),
    "short/OPUBL-1.0/head_800": (
        "GCR-docs\ttext\tno\t0.5215",
        _ROW,
    ),
    "short/PHP-3.01/tail_800": (
        "PHP-3.01\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/PostgreSQL/tail_300": (
        "PostgreSQL\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/RHeCos-1.1/tail_800": (
        "gSOAP-1.3b\ttext\tno\t0.9070",
        _OTHER,
    ),
    "short/SCEA/head_500": (
        "Apache-2.0\ttext\tno\t0.5889",
        _ROW,
    ),
    "short/SGI-B-2.0/tail_700": (
        "SGI-B-2.0\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/SGI-OpenGL/head_800": (
        "HPND-export2-US\ttext\tno\t0.8670",
        _KEPT,
    ),
    "short/SISSL-1.2/tail_1000": (
        "gSOAP-1.3b\ttext\tno\t0.4973",
        _ROW,
    ),
    "short/SL/tail_1500": (
        "HPND\ttext\tno\t0.5993",
        _ROW,
    ),
    "short/SNIA/tail_300": (
        "CUA-OPL-1.0\ttext\tno\t0.6986",
        _ROW,
    ),
    "short/Sendmail-Open-Source-1.1/tail_1500": (
        "BSD-1-Clause\ttext\tno\t0.7267",
        _ROW,
    ),
    "short/Spencer-99/head_700": (
        "BSD-2-Clause-pkgconf-disclaimer\ttext\tno\t0.6732",
        _ROW,
    ),
    "short/Sun-PPP/tail_800": (
        "ISC-Veillard\ttext\tno\t0.7147",
        _ROW,
    ),
    "short/Symlinks/tail_900": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/TCL/tail_1000": (
        "SWL\ttext\tno\t1.0000",
        _HELD,
    ),
    "short/TCP-wrappers/head_1500": (
        "BSD-4.3TAHOE\ttext\tno\t0.6851",
        _KEPT,
    ),
    "short/TU-Berlin-1.0/tail_700": (
        "HPND-Netrek\ttext\tno\t0.5949",
        _ROW,
    ),
    "short/TU-Berlin-2.0/head_800": (
        "HPND-Netrek\ttext\tno\t0.5576",
        _ROW,
    ),
    "short/TekHVC/tail_800": (
        "HPND\ttext\tno\t0.7522",
        _ROW,
    ),
    "short/ThirdEye/tail_900": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/UCAR/tail_1000": (
        "HPND-sell-MIT-disclaimer-xserver\ttext\tno\t0.7256",
        _ROW,
    ),
    "short/Unicode-DFS-2016/head_700": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/VOSTROM/head_1000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/Vixie-Cron/tail_1500": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/Xerox/head_2000": (
        "ISC-Veillard\ttext\tno\t0.5689",
        _ROW,
    ),
    "short/ZPL-1.1/tail_500": (
        "ZPL-1.1\ttext\tno\t1.0000",
        _RIGHT,
    ),
    "short/Zed/head_800": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/any-OSI-perl-modules/head_1500": (
        "APL-1.0\ttext\tno\t0.5155",
        _ROW,
    ),
    "short/blessing/tail_2000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/dvipdfm/tail_900": (
        "CPAL-1.0\ttext\tno\t0.5297",
        _ROW,
    ),
    "short/etalab-2.0/tail_1000": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/generic-xts/head_2000": (
        "dtoa\ttext\tno\t0.8472",
        _KEPT,
    ),
    "short/jove/head_700": (
        "SunPro\ttext\tno\t0.5556",
        _ROW,
    ),
    "short/lsof/head_1000": (
        "Spencer-94\ttext\tno\t0.8836",
        _KEPT,
    ),
    "short/pnmstitch/head_700": (
        "BSD-1-Clause\ttext\tno\t0.9089",
        _EXAMINE,
    ),
    "short/psutils/head_800": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "short/python-ldap/tail_800": (
        "pkgconf\ttext\tno\t0.5817",
        _ROW,
    ),
    "short/wwl/head_300": (
        "GPL-3.0-only\ttext\tno\t0.5070",
        _ROW,
    ),
    "short/xzoom/tail_700": (
        "Jam\ttext\tno\t0.4339",
        _ROW,
    ),
    "short/zlib-acknowledgement/head_800": (
        "Cube\ttext\tno\t0.8203",
        _ROW,
    ),
    "value/BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc.": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
    "value/Copyright (C) 2001-2005 by Vinay Sajip. All Rights Reserved. See LICENSE for license.": (
        "gSOAP-1.3b\ttext\tno\t0.6875",
        _ROW,
    ),
    "value/Copyright (C) 2004-2020 by Vinay Sajip. All Rights Reserved. See LICENSE for license.": (
        "TMate\ttext\tno\t0.6667",
        _ROW,
    ),
    "value/Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License": (
        "CECILL-2.1\ttext\tno\t0.5968",
        _ROW,
    ),
    "value/SEE LICENSE IN https://livekit.io/legal/terms-of-service": (
        "CC-BY-3.0\ttext\tno\t0.6604",
        _ROW,
    ),
    "value/apache-2.0 AND bsd-simplified-darwin AND (bsd-simplified AND public-domain AND bsd-new AND isc AND (bsd-new OR gpl-1.0-plus) AND bsd-original)": (
        "-\t-\t-\t-",
        _NO_ROW,
    ),
}
