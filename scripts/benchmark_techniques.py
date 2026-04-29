# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Benchmark: compare ranking techniques on artificial and realistic variations.

Techniques ranked
-----------------
  baseline : RapidFuzz token_sort_ratio + coverage scoring (production)
  dice     : Dice-Sørensen char bigrams + coverage scoring
  minhash  : baseline + MinHash Jaccard confirmation gate (ambiguous band)
  tlsh     : baseline + TLSH byte-hash confirmation gate (ambiguous band)

Architecture
------------
  Tier 1 (FTS5 recall) is shared by all techniques; we vary only Tier 2.
  Candidates are capped at 20 to keep ranking fast while retaining recall.
  normalize_text is cached per text hash.
  MinHash samples ≤ 200 word-trigrams (64 perms) for speed.

Variation sets
--------------
  artificial : fixture distortions at 1 / 5 / 10 %
  realistic  : copyright substitution, file header prepend,
               whitespace reformat, 30 % start snippet, 40 % mid snippet

Usage
-----
  python scripts/benchmark_techniques.py           # all 555 fixtures
  python scripts/benchmark_techniques.py --max 50  # quick smoke test
  python scripts/benchmark_techniques.py --licenses MIT,Apache-2.0
  python scripts/benchmark_techniques.py --verbose  # print misses
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text
from licenseid.types import CandidateMatch, InternalMatch

if TYPE_CHECKING:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "license-data"

# Candidates fetched from FTS5 for each query (balance recall vs. speed)
FTS5_LIMIT = 20

# Cap normalised query at this many words before ranking to avoid O(n*m)
# explosion on very long texts. 1500 words is well beyond what is needed
# to distinguish any two SPDX licenses.
RANK_WORD_CAP = 1500

_RNG = random.Random(42)

# ---------------------------------------------------------------------------
# Optional deps
# ---------------------------------------------------------------------------
try:
    import tlsh as _tlsh  # type: ignore[import-untyped]
    TLSH_AVAILABLE = True
except ImportError:
    TLSH_AVAILABLE = False

try:
    from datasketch import MinHash  # type: ignore[import-untyped]
    MINHASH_AVAILABLE = True
except ImportError:
    MINHASH_AVAILABLE = False

# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

_BIGRAM_CACHE: dict[str, frozenset[str]] = {}


def _bigrams(text: str) -> frozenset[str]:
    if text not in _BIGRAM_CACHE:
        _BIGRAM_CACHE[text] = frozenset(
            text[i : i + 2] for i in range(len(text) - 1)
        )
    return _BIGRAM_CACHE[text]


def dice_score(a: str, b: str) -> float:
    """Dice-Sørensen coefficient over character bigrams."""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return 2.0 * len(ba & bb) / (len(ba) + len(bb))


# MinHash: sample up to 200 word-trigrams, 64 perms (~4 ms for long texts)
_MH_PERMS = 64
_MH_MAX_SHINGLES = 200


def make_minhash(text: str) -> "MinHash":
    words = text.split()
    shingles = list(
        {" ".join(words[i : i + 3]) for i in range(max(1, len(words) - 2))}
    )
    if len(shingles) > _MH_MAX_SHINGLES:
        shingles = _RNG.sample(shingles, _MH_MAX_SHINGLES)
    m = MinHash(num_perm=_MH_PERMS)
    for s in shingles:
        m.update(s.encode())
    return m


# TLSH
_TLSH_STRIP = re.compile(r"[^a-z0-9 .,:;!?\-]")


def make_tlsh(text: str) -> str | None:
    if not TLSH_AVAILABLE:
        return None
    raw = " ".join(_TLSH_STRIP.sub(" ", text.lower()).split())
    h = _tlsh.hash(raw.encode())
    return None if (not h or h == "TNULL") else h


def tlsh_dist(h1: str | None, h2: str | None) -> int | None:
    if not TLSH_AVAILABLE or not h1 or not h2:
        return None
    try:
        return int(_tlsh.diff(h1, h2))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Realistic variations
# ---------------------------------------------------------------------------
_COPY_TMPLS = [
    "Copyright (C) {year} {org}. All rights reserved.",
    "Copyright {year} {org}",
    "Copyright (c) {year}, {org}",
]
_ORGS = ["Acme Corp", "Example Ltd.", "The Foo Project", "Widgets Inc."]
_YEARS = ["2018", "2020", "2022", "2024"]
_HEADERS = [
    "This file is part of the Foo project.\n\n",
    "# License\n\n",
    "---\nLICENSE\n---\n\n",
]

_REAL_LABELS = [
    "real_copyright",
    "real_header",
    "real_reformat",
    "real_snip_s",
    "real_snip_m",
]
_REAL_NICE = {
    "real_copyright": "Copyright sub",
    "real_header": "Header prepend",
    "real_reformat": "Reformat",
    "real_snip_s": "Snippet start 30%",
    "real_snip_m": "Snippet mid 40%",
}


def make_realistic_variations(text: str, idx: int) -> dict[str, str]:
    """Return a dict of realistic variation types."""
    words = text.split()
    n = len(words)

    cline = _COPY_TMPLS[idx % len(_COPY_TMPLS)].format(
        year=_YEARS[idx % len(_YEARS)], org=_ORGS[idx % len(_ORGS)]
    )
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    replaced = False
    for line in lines:
        if not replaced and re.search(r"copyright", line, re.IGNORECASE):
            new_lines.append(cline + "\n")
            replaced = True
        else:
            new_lines.append(line)
    copy_text = "".join(new_lines) if replaced else cline + "\n\n" + text

    end30 = max(20, int(n * 0.30))
    s40, e40 = max(0, int(n * 0.30)), min(n, int(n * 0.70))

    return {
        "real_copyright": copy_text,
        "real_header": _HEADERS[idx % len(_HEADERS)] + text,
        "real_reformat": " ".join(text.split()),
        "real_snip_s": " ".join(words[:end30]),
        "real_snip_m": " ".join(words[s40:e40]),
    }


# ---------------------------------------------------------------------------
# DB builder
# ---------------------------------------------------------------------------
_DB_KEEPER: list[LicenseDatabase] = []


def build_db(db_path: str, fixtures: list[Path]) -> LicenseDatabase:
    """Populate an in-memory DB and return the database object."""
    db = LicenseDatabase(db_path)
    _DB_KEEPER.append(db)  # keep alive for in-memory DB

    rows_lic: list[tuple] = []
    rows_idx: list[tuple] = []
    for fp in fixtures:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        norm = normalize_text(data["license_text"])
        rows_lic.append((
            data["license_id"], data.get("name", ""),
            data.get("is_spdx", True), data.get("is_osi_approved", False),
            data.get("is_fsf_libre", False), data.get("is_high_usage", False),
            len(norm.split()),
        ))
        rows_idx.append((data["license_id"], norm))

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.executemany(
            "INSERT INTO licenses "
            "(license_id, name, is_spdx, is_osi_approved, is_fsf_libre, "
            "is_high_usage, word_count) VALUES (?,?,?,?,?,?,?)",
            rows_lic,
        )
        conn.executemany(
            "INSERT INTO license_index (license_id, search_text) VALUES (?,?)",
            rows_idx,
        )
        conn.commit()

    return db


# ---------------------------------------------------------------------------
# Rankers
# ---------------------------------------------------------------------------

def _composite_score(sim: float, q_len: int, c_len: int) -> float:
    coverage = q_len / c_len if c_len > 0 else 0.0
    penalty = (1.0 - coverage) * 0.02 if coverage < 0.8 else 0.0
    bonus = 0.005 if 0.95 <= coverage <= 1.05 else 0.0
    return sim - penalty + bonus


def _sim_baseline(norm: str, st: str, q_len: int, c_len: int) -> float:
    if norm == st:
        return 1.0
    if q_len >= c_len * 0.8:
        # Full or near-full text: sort tokens then compare
        return fuzz.token_sort_ratio(norm, st) / 100.0
    if q_len >= 200:
        # Large snippet vs large text: token_set_ratio handles containment
        # correctly and avoids O(n*m) cost of partial_ratio on long strings.
        return fuzz.token_set_ratio(norm, st) / 100.0
    # Short snippet: use character-level alignment
    fast = fuzz.partial_ratio(norm, st) / 100.0
    if fast >= 0.6:
        aln = fuzz.partial_ratio_alignment(norm, st)
        if aln:
            window = st[aln.dest_start : aln.dest_end]
            return fuzz.token_sort_ratio(norm, window) / 100.0
    return fast


def _sim_dice(norm: str, st: str, q_len: int, c_len: int) -> float:
    if norm == st:
        return 1.0
    if q_len >= c_len * 0.8:
        return dice_score(norm, st)
    if q_len >= 200:
        # Large snippet: fall back to token_set_ratio for speed, then Dice
        # on candidate text (not window; Dice is character-level containment)
        return fuzz.token_set_ratio(norm, st) / 100.0
    # Short snippet: character-level alignment then Dice on window
    fast = fuzz.partial_ratio(norm, st) / 100.0
    if fast >= 0.6:
        aln = fuzz.partial_ratio_alignment(norm, st)
        if aln:
            return dice_score(norm, st[aln.dest_start : aln.dest_end])
    return fast


def _make_ranked(
    candidates: list[CandidateMatch], norm: str, sim_fn: object
) -> list[InternalMatch]:
    from typing import Callable
    sim_func: Callable[[str, str, int, int], float] = sim_fn  # type: ignore[assignment]
    qw = norm.split()
    q_len = len(qw)
    out: list[InternalMatch] = []
    for c in candidates:
        st = c["search_text"] or ""
        c_len = c["word_count"] or len(st.split())
        sim = sim_func(norm, st, q_len, c_len)
        out.append(InternalMatch(
            license_id=c["license_id"], base_score=sim, similarity=sim,
            coverage=q_len / c_len if c_len else 0.0,
            pop_score=c["popularity_score"], best_window=st,
            score=_composite_score(sim, q_len, c_len),
        ))
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def apply_minhash_gate(
    ranked: list[InternalMatch],
    q_sig: "MinHash",
    mh_idx: dict[str, "MinHash"],
    lo: float = 0.75, hi: float = 0.97, penalty: float = 0.90,
) -> None:
    changed = False
    for r in ranked:
        if lo <= r["base_score"] < hi:
            sig = mh_idx.get(r["license_id"])
            if sig and float(q_sig.jaccard(sig)) < 0.25:
                r["score"] *= penalty
                changed = True
    if changed:
        ranked.sort(key=lambda x: x["score"], reverse=True)


def apply_tlsh_gate(
    ranked: list[InternalMatch],
    q_hash: str | None,
    tlsh_idx: dict[str, str | None],
    lo: float = 0.75, hi: float = 0.97,
    threshold: int = 150, penalty: float = 0.90,
) -> None:
    changed = False
    for r in ranked:
        if lo <= r["base_score"] < hi:
            d = tlsh_dist(q_hash, tlsh_idx.get(r["license_id"]))
            if d is not None and d > threshold:
                r["score"] *= penalty
                changed = True
    if changed:
        ranked.sort(key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Result accumulator
# ---------------------------------------------------------------------------


class Result:
    __slots__ = ("total", "top1", "top3", "top5", "elapsed")

    def __init__(self) -> None:
        self.total = self.top1 = self.top3 = self.top5 = 0
        self.elapsed = 0.0

    def record(self, true_id: str, ranked: list[InternalMatch]) -> None:
        ids = [r["license_id"] for r in ranked]
        self.total += 1
        if ids and ids[0] == true_id:
            self.top1 += 1
        if true_id in ids[:3]:
            self.top3 += 1
        if true_id in ids[:5]:
            self.top5 += 1

    def acc(self, k: int = 1) -> float:
        n = {1: self.top1, 3: self.top3, 5: self.top5}[k]
        return n / self.total if self.total else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max", type=int, default=None, dest="max_n",
                   help="Limit to first N fixtures")
    p.add_argument("--licenses", type=str, default=None,
                   help="Comma-separated license IDs")
    p.add_argument("--rates", type=str, default="01,05,10",
                   help="Comma-separated distortion rates (default: 01,05,10)")
    p.add_argument("--verbose", action="store_true",
                   help="Print per-fixture misses")
    p.add_argument("--limit", type=int, default=FTS5_LIMIT,
                   help=f"FTS5 candidate limit (default: {FTS5_LIMIT})")
    args = p.parse_args()

    rates = args.rates.split(",")
    limit = args.limit
    filt: set[str] | None = set(args.licenses.split(",")) if args.licenses else None

    fixtures = sorted(FIXTURES_DIR.glob("*.json"))
    if filt:
        fixtures = [f for f in fixtures if f.stem in filt]
    if args.max_n:
        fixtures = fixtures[: args.max_n]

    if not fixtures:
        print("ERROR: no fixtures found. Run scripts/generate_dataset.py first.")
        return

    print(f"Fixtures : {len(fixtures)}")
    print(f"Rates    : {rates}")
    print(f"Cand lim : {limit}")
    print(f"TLSH     : {'yes' if TLSH_AVAILABLE else 'no (pip install python-tlsh)'}")
    print(f"MinHash  : {'yes' if MINHASH_AVAILABLE else 'no (pip install datasketch)'}")

    # ---- Build DB ----
    t0 = time.monotonic()
    db = build_db("file:bmark?mode=memory&cache=shared", fixtures)
    print(f"DB built in {time.monotonic()-t0:.1f}s\n")

    # ---- Pre-compute corpus indices ----
    print("Pre-computing corpus indices...")
    minhash_idx: dict[str, MinHash] = {}
    tlsh_idx: dict[str, str | None] = {}
    t0 = time.monotonic()
    for fp in fixtures:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        lid = data["license_id"]
        norm = normalize_text(data["license_text"])
        if MINHASH_AVAILABLE:
            minhash_idx[lid] = make_minhash(norm)
        tlsh_idx[lid] = make_tlsh(norm)

    print(
        f"  MinHash : {len(minhash_idx)} sigs  "
        f"TLSH : {sum(1 for v in tlsh_idx.values() if v)} hashes "
        f"({time.monotonic()-t0:.1f}s)\n"
    )

    # ---- Variation labels ----
    dist_labels = [f"dist_{r}%" for r in rates]
    all_labels = dist_labels + _REAL_LABELS

    techs = ["baseline", "dice"]
    if MINHASH_AVAILABLE:
        techs.append("minhash")
    if TLSH_AVAILABLE:
        techs.append("tlsh")

    res: dict[str, dict[str, Result]] = {
        t: {lbl: Result() for lbl in all_labels} for t in techs
    }

    # normalize_text cache keyed by text hash (avoids repeated BeautifulSoup)
    _norm_cache: dict[int, str] = {}

    def cnorm(text: str) -> str:
        k = hash(text)
        if k not in _norm_cache:
            _norm_cache[k] = normalize_text(text)
        return _norm_cache[k]

    # ---- Benchmark loop ----
    print("Running benchmark...")
    t_run = time.monotonic()

    for idx, fp in enumerate(fixtures):
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        true_id: str = data["license_id"]
        orig: str = data["license_text"]

        # All variation texts for this fixture
        texts: dict[str, str] = {}
        for rate in rates:
            key = f"license_text_distorted_{rate}"
            texts[f"dist_{rate}%"] = data.get(key, "")
        texts.update(make_realistic_variations(orig, idx))

        for lbl in all_labels:
            text = texts.get(lbl, "")
            if not text or not text.strip():
                continue

            norm = cnorm(text)
            if not norm.strip():
                continue

            # Cap query length for ranking — very long texts slow down
            # string metrics without improving accuracy.
            norm_words = norm.split()
            norm_rank = (
                " ".join(norm_words[:RANK_WORD_CAP])
                if len(norm_words) > RANK_WORD_CAP
                else norm
            )

            # FTS5 recall (shared Tier 1) — cap at `limit` candidates
            candidates = db.search_candidates(text, limit=limit)
            if not candidates:
                # Fallback: try normalised text (e.g. for reformatted)
                candidates = db.search_candidates(norm_rank, limit=limit)

            # Pre-compute query signatures once per variation text
            q_mh = make_minhash(norm_rank) if MINHASH_AVAILABLE else None
            q_tlsh = make_tlsh(norm_rank)

            # ---- baseline ----
            t0 = time.monotonic()
            ranked_base = _make_ranked(candidates, norm_rank, _sim_baseline)
            res["baseline"][lbl].elapsed += time.monotonic() - t0
            res["baseline"][lbl].record(true_id, ranked_base)

            if args.verbose and (
                not ranked_base or ranked_base[0]["license_id"] != true_id
            ):
                got = ranked_base[0]["license_id"] if ranked_base else "NONE"
                print(f"  [baseline] MISS {lbl:20s} true={true_id} got={got}")

            # ---- dice ----
            t0 = time.monotonic()
            ranked_dice = _make_ranked(candidates, norm_rank, _sim_dice)
            res["dice"][lbl].elapsed += time.monotonic() - t0
            res["dice"][lbl].record(true_id, ranked_dice)

            if args.verbose and (
                not ranked_dice or ranked_dice[0]["license_id"] != true_id
            ):
                got = ranked_dice[0]["license_id"] if ranked_dice else "NONE"
                print(f"  [dice    ] MISS {lbl:20s} true={true_id} got={got}")

            # ---- minhash gate (applied on top of baseline copy) ----
            if MINHASH_AVAILABLE and q_mh is not None:
                ranked_mh: list[InternalMatch] = [
                    InternalMatch(**r) for r in ranked_base  # type: ignore[misc]
                ]
                t0 = time.monotonic()
                apply_minhash_gate(ranked_mh, q_mh, minhash_idx)
                res["minhash"][lbl].elapsed += time.monotonic() - t0
                res["minhash"][lbl].record(true_id, ranked_mh)

            # ---- tlsh gate (applied on top of baseline copy) ----
            if TLSH_AVAILABLE:
                ranked_tlsh: list[InternalMatch] = [
                    InternalMatch(**r) for r in ranked_base  # type: ignore[misc]
                ]
                t0 = time.monotonic()
                apply_tlsh_gate(ranked_tlsh, q_tlsh, tlsh_idx)
                res["tlsh"][lbl].elapsed += time.monotonic() - t0
                res["tlsh"][lbl].record(true_id, ranked_tlsh)

        if (idx + 1) % 100 == 0:
            print(f"  {idx+1}/{len(fixtures)}  ({time.monotonic()-t_run:.0f}s elapsed)")

    total_s = time.monotonic() - t_run
    n_queries = sum(r.total for r in res["baseline"].values())
    print(f"Done: {n_queries} queries in {total_s:.1f}s "
          f"({total_s/n_queries*1000:.1f} ms avg/query)\n")

    # ---- Results table ----
    groups = [
        ("Artificial", dist_labels),
        ("Realistic", _REAL_LABELS),
    ]
    sep = "=" * (22 + 32 * len(techs))

    hdr1 = f"{'Variation':<22}"
    hdr2 = f"{'':22}"
    for t in techs:
        hdr1 += f" | {t:^29}"
        hdr2 += f" | {'Top1':>5}  {'Top3':>5}  {'Top5':>5}  {'ms/q':>5}"

    print(sep)
    print(hdr1)
    print(hdr2)
    print(sep)

    for gname, labels in groups:
        print(f"\n  {gname}")
        for lbl in labels:
            display = _REAL_NICE.get(lbl, lbl)
            row = f"    {display:<18}"
            for t in techs:
                r = res[t][lbl]
                if r.total == 0:
                    row += " |   N/A    N/A    N/A    N/A"
                    continue
                ms = r.elapsed / r.total * 1000
                row += (
                    f" | {r.acc(1)*100:>4.1f}%"
                    f"  {r.acc(3)*100:>4.1f}%"
                    f"  {r.acc(5)*100:>4.1f}%"
                    f"  {ms:>5.2f}"
                )
            print(row)

    print("\n" + sep)

    # ---- Delta summary ----
    other_techs = [t for t in techs if t != "baseline"]
    print(f"\nTop-1 delta vs baseline (pp = percentage points)\n")
    print(f"  {'Variation':<20}", end="")
    for t in other_techs:
        print(f"  {t:>10}", end="")
    print()
    print("  " + "-" * (20 + 13 * len(other_techs)))

    for gname, labels in groups:
        print(f"  {gname}")
        for lbl in labels:
            r_base = res["baseline"][lbl]
            if r_base.total == 0:
                continue
            display = _REAL_NICE.get(lbl, lbl)
            base_acc = r_base.acc(1) * 100
            row = f"    {display:<18}"
            for t in other_techs:
                r = res[t][lbl]
                if r.total == 0:
                    row += f"  {'N/A':>10}"
                    continue
                d = r.acc(1) * 100 - base_acc
                row += f"  {d:>+9.1f}pp"
            print(row)
    print()


if __name__ == "__main__":
    main()
