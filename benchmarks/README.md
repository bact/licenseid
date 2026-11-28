# Benchmarking — how it works

Recall/precision/speed/memory comparison between the current working tree
and `main`, across all input types the matcher handles. Implementation
notes for the actual scripts. The baseline of `bench_compare.py` is fixed in
the script to `main` (`baseline_label`); to compare with a release tag, change
that label.

## Running it

```bash
python benchmarks/bench_compare.py
```

- `--subset N` — stratified N-fixture subset for Type 3/4 fixtures only
  (Type 1, 2, 5, 5.1 always run in full). Shortens iteration cycles.
- `--fast` — reduced matrix: Type 3 tests `head_800` only (skips `head_300`
  and `head_500`); Type 4 tests `verbatim`/`02` only (skips
  `01`/`05`/`10`/`20`).
- `--verify` — 1-2 items per input type, for validating script changes
  without running the full matrix.

Full run with no flags takes about 2 hours.

## Architecture

- **`bench_compare.py`** — orchestrator. Creates a pristine `git worktree`
  of `main` in a temp dir (not a branch switch — avoids disturbing the
  working tree), runs `bench_single.py` against that worktree's `src/`,
  then against the current tree's `src/`, and diffs the two result sets
  into `benchmarks/summary.md`. Cleans up the worktree in a `finally`
  block.
- **`bench_single.py`** — runs one branch's evaluation in a subprocess
  (`sys.path.insert(0, <src_path>)` picks up whichever tree it's pointed
  at). Builds its own in-memory SQLite DB directly from the SPDX data
  tarball, bypassing `LicenseDatabase._update_db_records` — schema fields
  that a fixture or matcher path depends on must degrade gracefully or be
  built lazily, since this path won't populate them the way the real CLI
  does. Wraps the matcher in `InstrumentedMatcher` to record which tier
  (0 / 0.5 / 1 / 2) resolved each query. Measures wall time with
  `time.perf_counter()` and peak memory with `tracemalloc`. Writes one
  JSON result file per branch to `benchmarks/outputs/`. Its parts are
  `bench_single_db.py` (the database), `bench_single_matcher.py`
  (`InstrumentedMatcher`), `bench_single_fixtures.py` (the fixtures of each
  type), `bench_single_board.py` (the counters) and `bench_single_run.py`
  (the run and the result file). It also takes `--tarball PATH` (default:
  the newest tarball in the licenseid cache); `bench_compare.py` does not.
- **`bench_report.py`** — renders the two result sets as the Markdown of
  `summary.md`.

Both scripts are invoked as standalone processes (not imported), so a
branch's `src/` fully determines its behavior with no import-caching
cross-contamination between the two runs.

## Input types and fixtures

| Type | Fixtures | What it tests |
| --- | --- | --- |
| 1 — License IDs | `tests/fixtures/license-id/license_ids.json` | Each `id_*` field (`id_verbatim`, `id_deprecated`, `id_space`, `id_casing`, `id_punct`, `id_distorted`) should resolve to `license_id` |
| 2 — License names | `tests/fixtures/license-name/license_names.json` | `name_verbatim`, `name_space`, `name_casing`, `name_punct`, `name_distored` fields (the fixture file spells it so) |
| 3 — Short text | `tests/fixtures/license-text-short/*.json` | The `license_text_short_head_300`, `_500` and `_800` keys of each file |
| 4 — Long text | `tests/fixtures/license-text-long/*.json` | Clean `license_text` plus distortion variants (`01`/`02`/`05`/`10`/`20`; `20` is heaviest — character-level, breaks word tokens) |
| 5 — Mixed content | `tests/fixtures/mixed-content/` | Generated source/doc files with embedded license info, per canonical-ID directory |
| 5.1 — Mixed content (curated) | `tests/fixtures/mixed-content-curated/` | Same evaluation as Type 5, but hand-crafted fixtures instead of generated ones |

Stats are nested `stats[input_type][sub_category]`, each tracking
`total`/`top1`/`top3`/`top5` (plus per-tier resolution counts from
`InstrumentedMatcher`). `bench_compare.py` renders this into per-type
Markdown tables in `summary.md`.

## The speed gate (`speedgate/`)

`python -m benchmarks.speedgate` compares two frozen source trees of
licenseid. It records answers before time, and prints each gate of the
0.10.0 speed plan that its sets can answer
(`working-docs/design/speed-0-10-plan.md`, sections 6.1 and 6.2).

Rules, each learnt from a wrong number:

- A side is a frozen copy of a tree, named by path: `git archive <tag> | tar
  -x -C <dir>`. Never the checkout, never the editable install. Each set runs
  in a child process with `PYTHONPATH=<side>/src` (and a fixed
  `PYTHONHASHSEED`, a scratch `HOME`). The result holds `licenseid.__file__`
  of each set; `compare` prints it, and `WRONG IMPORT` if it is not the side's.
- Each side has a database it built itself with its own `update` from the
  cached List files, with a dead proxy, so no download is possible. The real
  cache folder is only read.
- The real files are a manifest of SHA-256 hashes over a local folder (the
  corpus), not a scan of what is installed that day. Files and manifest are
  other people's data and stay outside the repository.
- Both sides read one `inputs.json`; `compare` says if their digests differ.
- Time is CPU seconds (`time.process_time`), warm: a set of `detect()` cases
  runs once untimed over its own inputs (same inputs and options, results
  discarded), then timed (see "Warm-up" below). The first-call cost is the One
  call set. Every run records the 1-minute load
  (`uptime`) at its start and end; a run above 2.0 is flagged `loaded`.
- An A/A twin (the same side run twice) gives the noise floor: read it before
  a ratio.

### Running a comparison

All paths below are outside the repository (here under
`.claude/speed-0-10/`). Use Python 3.10 of the project environment, from the
repository root, with the repository root on `PYTHONPATH`.

```bash
R=.claude/speed-0-10
# 1. once: the corpus, then the inputs (fixtures of one side, a List tarball)
python -m benchmarks.speedgate corpus $R/corpus --onecall onecall.json \
    --labels labels.json --item68 item68.json
python -m benchmarks.speedgate verify $R/corpus
python -m benchmarks.speedgate inputs $R/corpus --side $R/sides/0.9.4 \
    --tarball ~/.local/share/licenseid/spdx-data-v3.29.0.tar.gz
# 2. for each side: a frozen copy, its database, its results
git archive <tag> | tar -x -C $R/sides/<name>
python -m benchmarks.speedgate db --side $R/sides/<name> \
    --db $R/db/<name>/licenses.db --home $R/home
python -m benchmarks.speedgate run --side $R/sides/<name> \
    --db $R/db/<name>/licenses.db --home $R/home \
    --inputs $R/corpus/inputs.json --out $R/baselines/<name>
# 3. compare (--twin: a second run of the base; --inputs: for the labels)
python -m benchmarks.speedgate compare $R/baselines/0.9.4 $R/runs/T3 \
    --twin $R/baselines/0.9.4-aa --inputs $R/corpus/inputs.json
```

`run --sets core stress` runs some sets only; a set whose result file exists
is skipped unless `--force`. Run a baseline alone on the machine, and run
nothing else beside it. `compare` exits 1 when a gate fails; an answer that
moved is listed first and read by a person, it is no gate by itself.

`corpus` needs `labels.json` (weak labels by file key, from the METADATA of
the package each file came with), `item68.json` (the keys of
`item68.item68_keys` over a 0.9.4 core result) and `onecall.json` (the ten
texts of the One call set). The README texts are the descriptions of the
installed packages that hold "licens".

### Sets

| Set | Inputs | Records |
| --- | --- | --- |
| core | 868: 300 real licence files, 408 long and 160 short fixtures | Top 3 rows, `TEXTS` of the top row, CPU |
| prose | 473: 300 READMEs, 96 notices, 77 mixed | Top 3 rows, `TEXTS` of the mixed (call) |
| many | 183: 2 to 40 texts joined, clean, 2 %, 5 % (165); 18 of cores | Rows, `texts()` |
| cjk | 24 re-wrapped Han and kana texts and fragments | Rows, `texts()` |
| options | 6 whole texts, each under 6 option settings | Rows, `TEXTS` |
| roadmap | Items 11, 61, 64, 68, 69, 70 (120) | Rows, `texts()`, CPU |
| headers | 158: the standard header of each of 79 licences, as given and cut | Top 3 rows, `TEXTS`, CPU, classes |
| stress | 18 large or odd inputs, one process each, limit 180 s | Rows, CPU |
| onecall | 8 files, 3 value commands, a fresh process, 11 runs | Milliseconds (minimum) |
| memory | Peak RSS at import, 1, 300 and 868 inputs | MB |
| threads | 4 threads on one detector, answers against one thread | Counts |
| damage | 26 damaged copies of the side's database (codes, postings, texts) | Rows against the intact build |
| versions | The side on a copy of the 0.9.4 database, 0.9.4 on a copy of the side's | Exit codes, lines, file states |

The Damage gate also damages the stored word-gram postings (a stale or missing
stamp, another gram size or width, a short or out-of-range blob, an emptied
table), and requires `gram_scores` of fixed inputs, the answers of the damage
inputs and the bytes of the damaged file to equal the intact build's; a side
without the postings tables (before build 8) records these kinds as not
applicable. The texts table is damaged too (missing, misshaped: not ready;
rows removed: as a rebuild without them); a side of build 9 or older damages
its FTS5 table instead.

The Versions set runs the side on a copy of the database of the last tag
(`<db>/0.9.4/licenses.db`, `SPEEDGATE_OLD_DB`) and the last tag's tree
(`<sides>/0.9.4`, `SPEEDGATE_OLD_SIDE`) on a copy of the side's database: each
lookup of the side exits 2 with `build vN outdated` and leaves the file as it
was (bytes, time, no file beside it), `update` makes its tables, rows and
answers those of a fresh build, `clear-cache` deletes it, and every command of
the last tag exits 2 with `database: invalid` and writes nothing.

Labels are not a run: `compare --inputs` counts agree, other and none of the
225 real files with one declared ID, at 0.85, 0.7 and 0.5, from the core
result. The roadmap set holds the real files of item 68 (the 23 that the
0.9.4 core run gives, with the 2 files of Pillow), the inputs of items 11 and
61 (a slice of Apache-2.0, MIT and HPND under copyright lines, six licences
under two copyright lines among them `RHeCos-1.1` and `BSD-ask-to-endorse`,
HPND's core), the licence files of wcwidth, mypy_extensions, certifi, numpy,
sympy and Pillow, and the HPND family of item 64. Item 62 (100,000 `License:`
lines) is a test of its own, not here. The 18 many-text inputs of cores are in
addition to the 165 of the plan.

Not measured by this tool, so `compare` prints them as not measured: the 462
PyPI values, the accuracy test, the golden answers, `--diff` and the
platforms. Storage alone is judged only by `compare --storage-alone` with a
`--twin` of the base: no field of any set moves, and core CPU within the
noise of the two base runs (3 percent at least).

### The headers set

The SPDX License List gives a `standardLicenseHeader` for 79 licences in use:
the notice a source file carries. `inputs` reads them from the List data
archive (`json/details/<ID>.json`, licences that are not deprecated), in
memory with `tarfile`, never extracted. The archive is `--headers-tarball`,
default the `--tarball` of the command; where the file is missing the set is
skipped and the command prints `headers: skipped`. `--name` writes the inputs
to another file name, so a new set never overwrites the file others read.
`run` skips a set that its inputs file lacks, with a printed line.

Two forms of each header: `hdr:given:<ID>`, as the List gives it, and
`hdr:cut:<ID>`, what a file's header holds word for word (rules in
`sets_headers.py`: a pair of `"` or `*` round the whole header dropped,
template-instruction lines dropped, each copyright statement cut up to its
holder or dropped, a placeholder left becomes the word `Example`; `[1]` and
`<https://...>` stay).

Verdict at the answer bar (0.85): right when the top answer is the header's
licence or one of its class, wrong for another licence, none below the bar. A
class is one normalised text, taken from the side's own database at the end of
the run (`headerclasses.py`, stored in the result as `classes`, so `compare`
needs no database): the `same_text` group (`-only` and `-or-later` twins, the
forms of GFDL whose texts are one), a deprecated ID with its replacement
(`superseded_by`, else its `-only` or `-or-later` form). An expression with no
row is a class of its own, so a compound answer is wrong.

### Warm-up

Before the timed pass, each in-process `detect` set (every set except
`stress`, `onecall`, `memory` and `threads`; `damage` runs it on each copy)
runs one untimed pass over its own inputs, with the same options and the
`texts()` call where the case has one. A side that reads the stored text of a
licence when it first becomes a candidate pays those reads in the untimed pass,
as 0.9.4 paid them in its one warm-up call, which loaded every text. The stress
set is a process a case and keeps one small call before the case. The one-call
set is cold on purpose: fresh processes, each reading the byte-code that one
untimed call wrote (every child keeps a byte-code cache under its scratch
home, whatever `PYTHONDONTWRITEBYTECODE` the caller has: an installed package
has one, and without it each call compiles every module of the side, which
added 20 to 40 ms to each call measured). The memory set is not warmed
either: it reports the peak after the import, after one input, after the real
files and
after the core inputs, so its last peak holds everything read during the run
and its earlier ones the growth. The threads set keeps its own first pass (one
thread, then four).

Results of 0.9.4 measured before this warm-up (`baselines/0.9.4`) stay
comparable: one text call already warmed everything there, and the pass
changed no answer (a `compare` of a run under the old and the new harness
shows no field differing). Re-running 0.9.4 with the pass gave CPU within the
noise of the stored numbers (a busy machine; run such a pair twice).

### Gates that `compare` prints

Core CPU (12 times), real file median (15 ms), One call (0.3 s; MIT and
BSD-3-Clause 0.15 s), no class slower (1.2 times, per input kind and per stress
input, kinds under 0.05 s are not judged), labels (agree 190, other 16),
fixtures (right not lower, wrong not higher), prose (the answer at 0.85 the
same; moved top rows at lower bars are shown, not judged), `TEXTS` (`texts()`
where a set records it; the `TEXTS` of the top row under the options and on
core where the answer is the same), roadmap inputs
(0.2 s), item 68 (no new answer on an HPND-family fragment), damage (equal to
the intact build, or to its reference where the text itself changed), threads,
memory (no peak over the base, 1 MB of slack), database size (under 20 MB),
versions (above),
headers (in each form no fewer right and no more wrong than the base; the
headers whose verdict moved are listed under "Headers"; not applicable when the
base has no headers results).

### Tests

`tests/test_speedgate.py` (manifest, builders, comparison and gates on made-up
results, no corpus or database needed) and `tests/test_speedgate_child.py`
(child process on a fake side, damaged copies, tarball; POSIX only, listed in
`tests/platform_files.py`, which skips it on Windows),
`tests/test_speedgate_headers.py` (forms, archive, classes, verdict, gate) and
`tests/test_speedgate_warmup.py` (warm-up on a fake side; POSIX only).

## Other paths worth knowing

- Real (non-benchmark) on-disk DB: `~/.local/share/licenseid/licenses.db`,
  built from `spdx-data-v3.29.0.tar.gz` in the same directory.
- Failure diffing: compare the `failures_sample` arrays (the first ten
  failures) between the two branches' JSON files in `benchmarks/outputs/`.

## Also in this directory

- `summary.md` — output of the most recent `bench_compare.py` run.
