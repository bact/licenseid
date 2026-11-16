---
Created: 2026-11-16
Last-Modified: 2026-11-17
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Resolved tech debt, from 0.5.0

Items of [`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md)
resolved from 2026-10-22 (0.5.0) on, in the order they were resolved. The
older ones are in [`tech-debt-resolved.md`](tech-debt-resolved.md); this
part was split from it on 2026-11-16, when it passed the file size limit.
Item numbers are the roadmap's.

- Two named-pipe tests could hang the suite (item 38, Priority 15;
  2026-10-22). `test_a_named_pipe_is_refused_rather_than_waited_on` and
  `test_no_uri_spelling_of_a_named_pipe_waits_for_a_writer` called
  `check_database_ready` in the test process: had the `_blocking_refusal`
  guard in `dbcheck.py` stopped working, the read-only open would have waited
  for ever, with no failure to read. They now run it in a child process with
  a 30 s timeout (`db_asserts.probe_check_does_not_hang`, beside
  `probe_does_not_hang`, both over `_run_probe`) and compare the child's
  `DatabaseNotReadyError` line. Mutation check: with the guard removed the
  test fails after the timeout, as `opening … hung`.
- A lone surrogate in a text raised `UnicodeEncodeError` (item 41, Priority
  20; 2026-10-22). The string met an encoder in SQLite's parameter binding,
  in the lookup by name that a tag value (or a short text) goes through. The
  CLI could send one too: Python decodes a byte of an argument that is not
  UTF-8 to `\udcXX` (`licenseid detect $'MIT\xff'` printed a traceback, exit
  1). Now `textinput.reject_lone_surrogate` raises
  `InvalidInputError` (`input: invalid: text: lone surrogate at character N`)
  at the one place the matcher takes a text (`_resolve_target_text`), so
  `detect`, `resolve_record` and the `is_*()` predicates agree, as they do for
  a `license_id`; the CLI checks `--text` and the argument first
  (`cli.reject_unencodable`) and exits 2. Not "no match": a text that cannot
  be read is the caller's mistake, and a silent `[]` would hide it.
- `GPL 2.0+` in prose lost its "+" in Tier 0 (item 30, Priority 6;
  2026-10-25). A value that is not SPDX-shaped went to Tier 0, which matched
  the normalised text, where the "+" is gone: `GPL 2.0+`, `GPL-2.0 +` and
  `LGPL 2.1+` answered their `-only` form. Now the version key (since 0.6.0
  `versionkey.version_key`) turns the "+" operator into "or later" before
  `normalize_text` drops it, read by the expressions' reader
  (`plusoperator.replace_plus_operator`), so
  `GPL 2.0+` and `LGPL 2.1+` answer `GPL-2.0-or-later` and
  `LGPL-2.1-or-later`. `GPL-2.0 +` has no operator (a "+" apart from its
  ID): it answers `GPL-2.0-only`, not exact, with
  `WARNING: match: variant not stated`. Not a guess from prose: the key
  must equal an ID's key, so a "+" after a license with no or-later form
  (`Apache 2+`, `C++`) finds none and goes on to the fuzzy name match, as
  before. Pinned in `tests/test_lone_expression.py` and
  `tests/test_version_key.py`.
- How deep an expression may be depended on the Python version (item 19,
  Priority 9; 2026-10-27). `py_spdx_license` walks its tree by recursion
  with no guard: Python 3.10 gave up at 335 operators in a row or 250
  brackets with an operator in each, 3.14 at 500 and 335, so one tag
  answered on 3.14 and not on 3.10. Now `identifiers.parse_expression`
  refuses over 150 operators or 150 levels of brackets before it parses
  (`_too_large_to_parse`, one pass), the same everywhere and within 3.10's
  limit. The test pinned as "either answer" now expects none. Pinned in
  `tests/test_plus_and_depth.py`, with the deepest shape the cap lets through
  parsed at a recursion limit of 1000.
- A missing file named as an argument was matched as text (item 32,
  Priority 24; 2026-10-27). `licenseid detect LICENSE.txt` with no such file
  answered `APL-1.0` at 1 and exited 0. Now an argument that names no file
  and is shaped like a path (one word, no URL, with `/` or `\` or a file
  name's extension such as `.txt`; `textinput.looks_like_path`) exits 2
  with `input: not found: <path>; pass --text`. No SPDX ID ends in a full
  stop and letters, so IDs, names and sentences are matched as before.
  The CLI matrix's E6 "relative file" cells named a `../mit.txt` that does
  not exist from their working directory and merged standard error into
  standard output (`2>&1`): the new error read as a diagnostic on stdout.
  They no longer merge the streams.
- An abbreviated ID with "+" became an invalid ID (item 39, Priority 18;
  2026-10-27). `identifiers._normalize_single_id` resolved the ID before a
  "+" by the shortest ID it prefixed, so `GPL-2+` gave `GPL-2.0-only+` and
  `MI+` gave `MIT+`, both exact. Now the ID before a "+" is read by ID or
  by its version key (`versionkey.named_row`, as `match()` reads it), and
  the "+" becomes the -or-later ID where the List has one in use: `GPL-2+`
  is `GPL-2.0-or-later`, `Apache-2+` stays `Apache-2.0+`, and `MI+` names
  nothing. A "+" after a stated qualifier (`GPL-2.0-only+`) names no
  licence: `identifiers.parse_declared` refuses it, and Tier 0 no longer
  drops a "+" to match the ID without it. The prefix lookup
  (`get_license_by_id_prefix`, `TableCache.active_id_with_prefix`) had no
  other caller and is gone; `tests/test_overlong_id.py` now guards the "+"
  path against long input. To read the version key without an import cycle,
  the "+" reader moved to `plusoperator.py` (standard library only) and the
  version key to `versionkey.py`.
- A licence URL was matched as text (item 45, Priority 12; 2026-11-08).
  `opensource.org/licenses/MIT` answered `any-OSI-perl-modules` at 0.87 and
  `spdx.org/licenses/MIT.html` `Parity-7.0.0`; a tag read the second as
  `MIT` and `resolve()` did not. Now `resolve()` reads a licence URL first
  of the name readers (`resolveurl.py`, category `license_url`), `detect()`
  answers a whole URL through it, and a tag and a field read it with the
  same reader (`url_license_id`). The key of a URL is `urlkey.url_key`; the pages
  are the List's own (`spdx.org/licenses/<ID>`, `spdx:<ID>`), the pages of
  hosts that end in an ID, the `seeAlso` of the List (new `license_urls`
  table, `records.BUILD_VERSION` 4) and a short table of aliases. A page of
  several licences or of an exception is refused with a reason; no host
  outside the table is read by its path. Details:
  `licence-urls.md`. PR for #14 (no number yet).
- `detect(file_path=<missing>)` raised a bare `FileNotFoundError` (item 35,
  second bullet; 2026-11-09). `textinput.read_text_file`, the one reader of
  user input, now raises `InvalidInputError` (exit 2, as `binary file` and
  `empty`): `input: not found: <path>`, `input: unreadable: <path>: <reason>`
  for a permission error or a path that is no regular file (a directory, a
  named pipe, which is never opened), `input: invalid: file path: <reason>`
  for an empty path, a NUL or a lone surrogate. The CLI already exited 2 for
  these; only the reason for a directory changed (`not a regular file`).
  PR (no number yet).
- A "+" that is no operator was dropped and the answer was exact (item 44,
  Priority 12; 2026-11-09). #149 fixed bare values, tags and fields; three
  paths still answered `MIT` exact at 1.0 while `resolve()` refused the
  value: quoted or bracketed text (`"MIT++"`, `[MIT++]`, `"MIT +"`), a name
  (`MIT License++`, `Apache License 2.0++`, `GPL-2.0 or later+`,
  `Apache 2.0 +`) and a quoted manifest read by the CLI with no extension.
  `normalize_text` drops a "+", so the text match found the licence round
  it. Now `detector._try_tier0_short_text` returns None for a value under 30
  words that `resolve()` refuses with a reason of the "+" family
  (`resolvereason.is_plus_refusal`; the reason, not the category, because
  some are `unresolved`): a whole input gets no answer and the warning
  `too few words for text`, a field is skipped silently. `normalize_text`
  is unchanged (no `NORMALIZATION_VERSION` bump). A long text (a `C++`
  line) never reaches the check; a value of 10 words or more that is a
  compound with such an operand still goes to Tier 1 (a text, by
  `MIN_TEXT_WORDS`). Left: a "+" in prose (item 47), wrappers `resolve()`
  does not read (item 48). Test: `tests/test_stray_plus_paths.py`, the
  invariant `plus_refusal_has_no_answer` of the harness.
- A tag value with a non-ASCII letter was cut short (item 33, Priority 12;
  2026-11-09). `LicenseRef-café` was read as `LicenseRef-caf`. The refusal
  was already in place (`exprtokens.cut_inside_word` in
  `identifiers.leading_expression`: an ID cut inside a word is no
  expression, as an idstring holds ASCII only, SPDX 3.0.1), so every entry
  point answered nothing, and `resolve()` refuses with `not found: …` or
  `operand not resolved: …`. What was missing was a word: the tag path of
  `detect()` now warns `input: invalid: <value>` (`markers._cut_by_non_ascii`,
  on `identifiers.read_leading`), once per distinct tag value; a valid ID with
  no match, prose after an expression (`MIT ü`) and a mark that is no
  letter (`MIT€`) stay quiet. Test: `tests/test_tag_invalid_warning.py`,
  `tests/test_tag_edge_values.py`.
- Expressions and references carried the wrong flags (item 34, Priority 12;
  found done 2026-11-09). `exprflags.py` judges them: a `LicenseRef-*` is
  `is_spdx` false with both approval flags null; for an expression `OR` is
  true if any operand is, `AND` only if all are, `WITH` takes its licence;
  the text record keeps a value's spaces in `EXPRESSION=` with tab-separated
  fields. Checked by `detect --json --id LicenseRef-x` and a tag with
  `MIT OR Apache-2.0`.
- Conflicting options and inputs were resolved silently (item 5, Priority
  15; 2026-11-09). By the time of this pass most was done: two inputs (CLI
  `--id`/`--text`/argument, API `license_id`/`file_path`/`text`) exit 2 or
  raise `InvalidInputError`; `--json` with `--diff` exits 2; `--top` and
  `--threshold` out of range exit 2; `--bold` never existed. Decided: an
  option with no effect on an exact answer is documented, not rejected
  (`--diff` with `--exact`: an exact result has no diff; `exclude`,
  `only_spdx`, `only_common`, `hint`, `enable_popularity` with an explicit
  `license_id`, a bare ID or name, or a tag). Added: `detect()` raises
  `TypeError` for an option of the wrong type (`in
  detectrequest._check_option_values`), as it does for a `text` that is no
  `str`: `exclude="MIT"` was read as a string and kept every ID that is a
  substring of it. Tests: `tests/test_match_options.py`,
  `tests/test_public_surface.py`.
- Tier 0 and wrappers `resolve()` does not read (item 48, Priority 12;
  2026-11-09). Tier 0 read the normalised text of a short value that
  `resolve()` refuses, so the wrapper and the "+" were gone: `「MIT++」` was
  `MIT`, `「GPL-2.0+」` `GPL-2.0-only`, `<MIT>` and `*MIT*` `MIT`, and a
  quoted INI `GPL-2.0+` lost its operator. Now
  `detector._try_tier0_short_text` asks `resolve()` first (what it reads is
  the answer, for a field too: a title, a name, a compound), and a value it
  refuses gets no text match after a dropped mark, an unpaired bracket
  (`parse failed`) or a "+" that ends a word, under 10 words
  (`resolvereason.refuses_text_match`; `C++`, `g++` and a "+" apart in the
  middle are no such word). `MIT)` and `GPL-2.0/+` lose their answer too.
  The first version of the fix refused any "+" and dropped the ID reader;
  the review (a README line with `C++`, `OSL-3 0`) showed both lost right
  answers.
  Decided with the user: `<>` and `*` are refused as `resolve()` refuses
  them; `「」` and `『』` become quote marks (`quotes.CORNER_PAIRS`), not
  folded by `normalize_text`, so no `NORMALIZATION_VERSION` bump; `BSD (3
  clause)` and `BSD (3-clause)` (2 projects of the fixture) join
  `resolvealias.ALIASES`. Removed: the lone-expression and loose-`WITH`
  readers of Tier 0. `looseid.loose_with` stays (`license_id=`). Left:
  item 50. Tests: `tests/test_tier0_wrappers.py`, `tests/test_stray_plus_paths.py`,
  the goldens of `tests/harness_changes_wrappers.py`.
- Cargo's `MIT/Apache-2.0` was matched as text (item 43, Priority 16;
  2026-11-09). The roadmap text was stale by then: `detect(text="MIT OR
  Apache-2.0")` already answered `Apache-2.0 OR MIT` (`resolvefirst`), and
  `MIT/Apache-2.0` answered nothing, with `too few words for text`, not
  `ECL-2.0`; the golden file still recorded the old guess. Cargo fields read
  `/` through a second, looser reader (`manifest._cargo_or`, any word,
  case folded). Now `resolveslash.py` is the one reader: a whole value of
  two or more pieces cut at `/`, each a List ID spelt exactly as listed
  (a "+" as `plusoperator` reads it) or `LicenseRef-*`, at least one a List
  ID, is `A OR B` with a `separator` step (detail `slash as OR`). Decided:
  - no case fold (`zlib/libpng` would be `Libpng OR Zlib`; the author means
    `zlib-acknowledgement`), so a lower-case Cargo value is lost
    (`_cargo_or` deleted);
  - a table of refused pairs, `MIT/X11` only (Debian's name of one licence);
  - a tag does not read `/` (its value runs on into prose); a field does;
  - the step kind `separator` is reused: a new kind that is no category
    would leave the value `exact` (`resolveleaf.category_of`).
  Names with a `/` on the List (12 licences, 2 exceptions) stay refused.
  Tests: `tests/test_resolver_slash.py` (accepted and refused tables, the
  refused ones pinned to 0.8.3's full answers in `tests/slash_pins.py`),
  `test_resolver_slash_props.py` (every ID beside `MIT`, random pairs,
  perturbed operands, names with a `/`), `test_slash_detect.py` (two
  databases, pinned to `main`), `test_slash_fields.py`, `test_slash_cli.py`,
  `test_slash_timing.py`, `test_slash_corpus.py`. Moved: `MIT/Apache-2.0`
  in the parity corpus, the PyPI sample and the `detect()` golden. Out of
  scope and still wrong: `License: MIT/Apache-2.0` answers `Apache-2.0` by
  name, not exact; a tag `MIT/x` answers `MIT`. (`/MIT` answered `MIT` exact
  through Tier 0 while `resolve()` refused it; PR #195 made `detect()` agree.)

- The loose `License:` field reader resolved every match (item 23, Priority
  12; 2026-11-15). `MarkerDetector._detect_explicit_identifiers` looked up
  each `license:`/`license =` match and made a candidate of each licence
  that resolved. The lookups were not the main cost: 10,000 lines of
  distinct real IDs took 0.47 s there but 14 s in `detect()`, because each
  of the 715 candidates then cost a similarity score (about 18 ms). Now it
  reads each distinct stripped value once, at most
  `candidates.FIELD_VALUES_READ` (256) of them, lazily
  (`candidates.first_distinct`), and keeps at most
  `FIELD_LICENSES_KEPT` (48) licences. The first match does not stop the
  read: `License: MIT` and `License: Apache-2.0` on two lines are two
  candidates, as before.
  - Measured on Python 3.10, the real database, 10,000 lines: cycled real
    IDs, the reader alone 7.55 s to 0.05 s, `detect()` 13.2 s to 3.3 s (715
    candidates to 105 results; the same text with the reader off takes 2.7
    s); `License: MIT` repeated 1.3 s to
    0.9 s; distinct unresolved values 2.4 s to 2.2 s (the rest is the text
    tiers, not this reader). The regex itself is linear (100,000 lines in
    0.02 s). Of 6,455 texts (SPDX 3.29 and the fixtures) none held more than
    one resolving value, and the most distinct values in one was 5. A notice
    file lists one licence per package, so a first cap of 16 (reviewer's
    finding: 20 licences lost 3) became the two bounds above; a second review
    found a DEP-5-style notice of 40 licences ending in the MIT text, which
    a cap of 32 answered MIT-0, so the second bound went to 48).
  - The INI cost was not Python 3.10 alone (the roadmap said 0.3 s on
    3.14): `[a]` followed by 100,000 bad lines took 2.8 s on 3.10 and 3.3 s
    on 3.13, because `ParsingError.append` joins by `+=`; a later 3.14
    patch release (3.14.10) joins the parts (`ParsingError.combine`) and
    takes 0.35 s. `manifest._has_bad_ini_line`
    now finds the first line that is no header, option or continuation, and
    `ini_license_values` answers None there. It follows configparser's
    default rules and judges one way only: a line it calls bad raises in
    configparser. `test_many_bad_lines_read_in_linear_time` therefore guards
    only the Pythons that still append (3.10 to 3.14.3 at least; CI's 3.10
    runs it).
  - Tests: `tests/test_license_field_reader.py` (answers pinned before the
    change, the cap boundary, lookup counts, timing),
    `tests/test_ini_bad_lines.py` (the one-way rule against every pair of
    lines and 4,000 random files, timing). Neither file is in
    `tests/platform_files.py`: no file system, stream or encoding.

- A database truncated during a block crashed with SIGBUS (item 40,
  Priority 20; 2026-11-15). Cutting the file (`truncate`, `: >`, a `cp` in
  progress) while a `reading()` block held its connection, or while a
  statement ran, killed the process with SIGBUS (exit 138 on macOS, 135 on
  Linux) and no message. Between two statements only a cut to 0 crashed;
  during a statement every cut did. Cause:
  `PRAGMA mmap_size=268435456` in `Connections.connect`, a mapped page past
  the new end of file. Now the pragma is gone and the lookup raises
  `DatabaseNotReadyError`.
  - Measured on a copy of the real database (macOS arm64, Python 3.10, SQLite
    3.50.4; English texts and 48 Japanese and Chinese slices; top answers
    identical): English set 12.01 s with the pragma, 11.49 s without; CJK
    set 9.22 s and 8.85 s; 1,800 `detect(license_id=...)` 0.371 s and
    0.350 s; first match in a new process, ratio median 1.000. The 2026-07
    gain of about 35% dates from when every query opened its own connection
    (`speed-optimizations-round-2.md`, item 5); `reading()` replaced that.
  - Rejected: a 4 MB map (still crashes on a cut to 0); no map on the shared
    connection only (a cut during a statement outside a block still
    crashes); a size check before each query (racy, misreads a replaced
    file); a SIGBUS handler in Python (the faulting instruction re-runs, the
    process hangs).
  - Still open: SQLite maps the `-shm` file of a WAL database whatever
    `mmap_size` says; a cut `-shm` of a database left in WAL by an old version
    still kills the process (item 53). Not measured: a cold page cache, Linux.
  - Tests: `test_file_cut_between_queries_of_a_block` (child process; cut to
    0, 1 byte, a page, mid-page, cut and extended, half rewritten, replaced)
    and `test_file_cut_while_a_statement_runs`, in
    `tests/test_lookup_database_errors.py` (already in `platform_files.py`).

- Environment failures in the database path (item 10 and a bullet of item 46;
  2026-11-15). `update` with a default directory it cannot make said
  `database: update failed: PermissionError: ...`; it is now `directory:
  write failed: <dir>: <reason>; pass --db` (`datadir.make_default_dir`,
  exit 1). `--db file://localhost/abs.db` was already fixed (commit 1cbc867;
  `test_absolute_file_uri_spellings_are_ready`). A database path that loops
  through symlinks was already refused before any download, but `update` and
  `clear-cache` called it `invalid`: it is `unreadable` now
  (`dbcheck._symlink_loop`), and `dbcheck.is_absent` replaces `lexists` so a
  loop above the file no longer reads as missing with a `run 'licenseid
  update'` hint. A dangling link into a missing directory is refused before
  the download too. `clear-cache` removes a cache file that is a looped or
  dangling symlink (`spdx_source.clear_cache_files`; `exists()` is False for
  one). Tests: `tests/test_db_path_loops.py`.

## Item 46, part (PR #210, 2026-11-15)

- `detect()` options typed as `DetectOptions` (`Unpack`), `ID_COLLECTIONS`
  from one alias; `docs/python-api.md` says where `exclude`, `hint`,
  `only_spdx`, `only_common` act. No answer moved. The gaps stay open in
  item 46 as decisions (pinned `# BUG:`/`# DECISION:` in
  `tests/test_detect_options_paths.py`, an axis set of its own).
- Lock-wait test of `LicenseDatabase` made event-driven. Mutation check:
  `timeout=0` on the connects fails it. The editable install imports the
  main checkout: run mutants with `PYTHONPATH=<worktree>/src`.
- One long-text database build (`tests/long_text_db.py`), shared by the
  harness and `test_accuracy`: sorted-row hashes of `licenses`,
  `license_index` and fingerprints identical before and after.

## Item 46, part (PR #211, 2026-11-16)

- `exclude` and `hint` act on free text only (`idoptions.py`), as decided
  for item 52 on 2026-11-15. A declaration (a tag, a field, `license_id`,
  a whole input `resolve()` reads) is never filtered or hinted. `exclude`
  now also drops prose-marker, mixed-content window and short-prose name
  hits (`exclude=["GPL-2.0-only"]` answered `GPL-2.0-only` at 0.9955 from
  a marker). Both fold case (`listlookup.fold_case`); a hint given twice
  is added once. A bare deprecated ID stands for both twins and `GPL-2.0+`
  for the `-or-later` one, each once per call with `WARNING: option:
  deprecated ID: exclude GPL-2.0; using GPL-2.0-only, GPL-2.0-or-later`
  (`upgraded_options`, called once in the detector's context, so no path
  warns twice); a `-with-` ID is taken as written. Tests:
  `tests/test_exclude_hint_free_text.py` and the moved pins of
  `tests/test_detect_options_paths.py`. Still pinned `# BUG:` and open in
  item 46: a hint undoes `exclude` and passes `only_common`/`only_spdx`; a
  hint counts towards the fewer-than-5 test of the mixed-content search.

## Item 52 (PRs #211 and #212, 2026-11-16)

- A bare deprecated ID such as `GPL-2.0` stays as written in `detect()`, as
  in `resolve()`; a text match never gives a deprecated ID (an "or later"
  grant of the same family in the text gives `-or-later`, else `-only` with
  `WARNING: input: variant not stated`). `--variant
  auto|as-written|only|or-later` (API `variant=`) is a preference that never
  overrides stated words (`WARNING: option: overridden by input`). The last
  record field is `VARIANT_STATED` (JSON `variant_stated`). `exclude` and
  `hint` stay `detect()` options and act on free text only (PR #211, listed
  above under item 46).
- `EXACT` follows how the answer was reached: true when a list defines it or
  the text is identical, false for a rewrite rule (`separator`,
  `prose_form`, `version_spelling`) and for a variant licenseid chose.
  About 7.5% of resolved values of the PyPI sample flip to false; 11 long
  golden answers moved (`tests/harness_changes_exact.py`).
- `is-osi` and `is-fsf` judge a kept bare ID by its `-only` and
  `-or-later` twins, and a `-with-` ID as `<bare>-only WITH <exception>`.
- Results carry `types.Evidence`; `variants.stated_of` is the one reader of
  `VARIANT_STATED` (fail closed), `Evidence.decided` marks the forms licenseid
  chose. The leftovers stay open as item 52 of the roadmap; the design, the
  paths rejected and the pinned cases are in
  [`item-52-variant-and-exact.md`](item-52-variant-and-exact.md).

## Item 42 (PR #216, 2026-11-16)

- A very long word cost seconds in the full-text search (item 42, Priority
  16; 2026-11-16). Found by PR #82's Windows CI. A quoted query word is a
  phrase of its trigrams, so the `MATCH` of `search_candidates` cost time
  in the word's characters, and the probe gate guards only RapidFuzz. On the
  real database one query on 10,000 characters of `the` took 1.22 s (50,000:
  7.9 s; 200,000: 34.8 s); `x` repeated cost a twentieth of that; random
  letters and Japanese under 0.01 s (an absent trigram ends the phrase). The
  new `ftsquery.match_query` (standard library only) builds the string: the
  first `MAX_TERMS = 20` words, each cut to `MAX_TERM_CHARS = 128`
  characters before `"` is doubled (a cut after quoting can leave a lone
  `"`, an FTS5 syntax error). Why 128: the longest word of any indexed text
  of List 3.29.0 is 70 characters (CAL-1.0; CC-BY-SA-2.1-JP 62), and a query
  word has no space, so a word cut to N of at least 70 matches what it
  matched before (nothing, if it was longer; itself, if not): the cut changes
  no Tier 1 result. This answers the CJK lesson of item 16: a Japanese run
  over 70 characters matches nothing today either. It is a cut, not a drop,
  so a future List with a longer word still finds it by its prefix.
  - Measured against `main` on the real database, `detect()` on ten words
    plus one long word of 60,000 characters: `the` 20.2 s to 0.20 s, `x`
    1.13 s to 0.18 s, five distinct words of 12,000 characters 11.0 s to
    0.23 s, three `license` keywords each followed by a 20,000-character
    word 9.9 s to 0.21 s; Japanese and random letters were already 0.2 s.
    2,000,000 characters of `the`: 5.6 s after, of which Tier 2 takes
    about 6 of 9 s under a profiler (RapidFuzz, 0.12 s per candidate:
    the cost of item 16 and 11, not of this query); Tier 1 alone is
    0.02 s.
  - Sweep: 1,668 slices of every fourth long-text fixture (offsets 0, 25,
    50, 75 per cent; 50, 200, 1,000 words, Han and kana 100, 500, 2,000
    characters) on `main` and the branch: top three answers and scores
    identical. `benchmarks/bench_fts5_recall.py` on 695 fixtures: head,
    tail and union recall identical. `python -m tools.golden`: no answer
    moved.
  - `tests/test_ftsquery.py` pins the query of every long-text fixture
    (head and tail windows) to the old builder, holds the longest word of
    those fixtures below the cut (555 files; a new List with a longer word
    fails it: re-decide), and times a 60,000-character word on the
    real-sized fixture database (`tests/long_text_db.py`): a 5-row index ran
    the same query in 0.04 s on `main`, so it cannot fail there.

## Item 56 (2026-11-16)

`python -m tools.cli_matrix --check` flagged cell `E8-011` ("file is a FIFO
with writer") as a hang: a 120 s timeout.

- Cause: a harness artefact, not a `licenseid` hang. Since PR #184 `detect`
  refuses a non-regular file without opening it (exit 2, `input:
  unreadable: ... not a regular file`), so the cell's background `printf >
  $W/ff` never found a reader. It blocked in `open()`, held the cell's pipes,
  and the runner waited for them until the timeout. The writer also outlived
  the run.
- Cell: the writer drops its standard streams (`exec >/dev/null 2>&1`), and
  the cell frees it after `detect` with a read-write open (`: <>$W/ff`). It
  has no `wait` or `kill`, which would switch off the judge's exit and output
  checks (`judge.has_pipe_tail`); it now expects exit 2, empty standard
  output and the refusal line.
- Runner: a plain cell runs in its own process group; a timeout or Ctrl-C
  kills the group (also on the terminal runner), and the read after the kill
  is bounded.
- Tests: `tests/test_cli_matrix_fifo.py`; a FIFO with a blocked writer is
  refused, not opened, in `tests/test_textinput.py`.

## Item 54 (PR #217, 2026-11-16)

- A truncated ID got an answer (item 54, Priority 12). `Apache-1` was read
  as `Apache-1.0` because `versionkey.version_key` folds `N.0` to `N`, and
  `MIT-` as `MIT` because a loose reading drops a joiner. Both are refused
  now.
  - **Bare major with a sibling minor.** `versionkey.writes_bare_major`: the
    last `[0-9]+(\.[0-9]+)*` of the text is all digits (a trailing `.` is no
    part of it). `sibling_keys`: a key that is the text's key with one or more
    numbers inserted right after its last number (`apache 1 1`, `lgpl 2 1
    only`, `python 2 0 1`; `cc by 3 de` is no sibling of `cc by 3`).
    `ambiguous_ids(db, text)` gives the sorted IDs of the row and its
    siblings, deprecated rows included, or nothing for a row that is an
    `-or-later` form or ends in "+". `looseid.loose_id` gives None for it
    unless `granted=True`; `resolveleaf._base` raises `_Ambiguous`, which
    `_read` turns into `unresolved`, reason `version ambiguous: <IDs>` (cut at
    60 characters), no step. `_plus`, `_single`'s grant branch, `_grant` and
    the two "does it name a licence" checks pass `granted=True`: a grant
    covers every later minor (`LGPLv2+`, `Apache-1+`, `LGPLv2 or later`).
    The reason is in `resolvereason._NO_TEXT_CONDITIONS`, so Tier 0 gives no
    fuzzy answer; `loose_with`, `shorttext` and `--id` get None from
    `loose_id`. The List has 35 such keys (the sweep is in the shared notes of
    the session): the `-2.0` of `AFL`, `CC-BY*`, `CECILL`, `LGPL` (and `-only`,
    `-or-later`), `OLDAP`, `OSL`, `ZPL` and the `-1.0` of `Apache`, `CDDL`,
    `EUPL`, `LPPL`, `MPL`, `OFL` and more. A patch-only sibling counts
    (`Python-2` for `Python-2.0.1`).
  - **Trailing joiner.** `dropguard.trailing_joiners`: a run of `-`, `_` or
    any dash of `normalize.RE_DASHES` after a letter or digit at the end of
    the text, one `.` or `,` after it left out; not on a `LicenseRef-*` or
    `AdditionRef-*`. `_base` joins it to `dropped` (reason `character dropped:
    U+002D`, a `drop` step) except for a head before a grant
    (`GPL-2.0-or later`, whose gap `classify.grant_head` judges). `dropped`
    itself is unchanged, so `classify._kept` reads as before. `MIT--` (pinned
    as staying), `Apache 2.0-`, `GPL-2.0 or later-`, `BSD 3-Clause-`,
    `GPL-2.0-only-` and `MIT_` flip; `MIT.-` and `MIT -` do not.
  - **Moved**: `LGPLv2` in the PyPI sample (`resolver_changes_cutversion.py`);
    11 golden answers (`harness_changes_cutversion.py`), each a wrong or
    doubtful answer (`id/Apache-1.1/id_distorted` read `Apache-1.0`,
    `id/AFL-2.1/id_distorted` read `AFL-2.0`).
  - **Tags** (owner decision, 2026-11-16, after the first build kept them):
    `identifiers.read_leading` ends a tag expression at the first token no
    operator bridges, so `SPDX-License-Identifier: MIT-` was `MIT`,
    `EXACT=true`. `dropguard.cut_by_joiners(text, end)`: a run of `-`, `_` or
    a dash of `RE_DASHES` touches the expression's end and the value ends, or
    white space or one of `.,;:!?+"')` follows; then it is no expression, as
    the argument is. Any other character after the run (`MIT-->`, `MIT-*/`,
    `MIT-}`, `MIT--]]`) is left alone: the reader knows no comment closers,
    and `-->` must read. A
    dash apart (`MIT - text`) is the author's. Perf: linear in the run (50,000
    dashes 51 ms against 43 ms on `main`); a refused line falls to the text
    tiers as any unreadable line does. Two readers changed with it: a tag
    reference takes the dashes at its end (`exprtokens.ref_end`), so
    `LicenseRef-a-` is `LicenseRef-a-` as `resolve()` reads it (it was
    `LicenseRef-a`), and `classify.dash_gap` takes `_` as it takes a dash
    before a grant (`GPL-2.0_ or later` still reads).
  - Left as they were, on purpose: the trove classifier `(LGPLv2)` is
    `LGPL-2.0` from `trovenames`; `--variant or-later LGPLv2` is refused, not
    widened. Measured cost: 115 distinct bare majors
    in one compound take 16 ms against 10 ms on `main`, linear in the operands.
  - Tests: `tests/test_cut_versions.py` (pins written on `main` first, flipped
    here), the rows of `test_resolver_small_refusals.py`,
    `test_resolver_lists_and_reasons.py`, `test_resolver_dropped_words.py` and
    `test_version_key.py`; for tags `tests/test_cut_tags.py` and
    `test_tag_edge_values.py`.

## Item 9 (2026-11-17)

`scripts/`, `benchmarks/` and `tools/` were not linted in CI (it checked
`src/` and `tests/`, and `mypy` on `tools/`). Measured on `main`: ruff clean
in all three; flake8 11 findings in `scripts/`, 14 in `benchmarks/` (which
`.flake8` excluded), 5 in `tools/`; pylint 8.89, 9.59 and 9.83 out of 10.

- **Fixed**, no behaviour change: `generate_fixtures.py` (755 lines) is split
  with `fixture_distort`, `fixture_mixed` and `fixture_dirs`; `bench_single.py`
  (774 lines) is an argument parser over `bench_single_matcher`, `_board`,
  `_db`, `_fixtures` and `_run`; `bench_compare.py` keeps its flow and
  `bench_report.py` renders the summary; `bench_fts5_recall.py` and the long
  functions of `tools/cli_matrix` (`judge`, `launcher`, `cells/detect`,
  `cells/update`) are split. No ceiling in `pyproject.toml` or `.flake8` was
  raised.
- **Equal output checked**: `generate_fixtures.py` on synthetic licences
  (57 files, byte-equal); `bench_single.py` (`--subset 3 --fast`, `--verify
  --fast`) and `bench_fts5_recall.py` (695 fixtures) equal but for timing and
  memory; the summary of `bench_compare.py` byte-equal on three real result
  pairs; `build_cells()` (1,256 cells) equal. Not run: the 2-hour
  `bench_compare.py`, the real SPDX download of `generate_fixtures.py`, a full
  `bench_single.py`, `python -m tools.cli_matrix`.
- **A bug found**: `bench_single.py` crashed on the current `src` (`detect()`
  returns `expression`, no `license_id`) and named a type that does not exist
  (`DetectRequest`, now `DetectOptions`). `id_of()` reads `license_id` first,
  then `expression`, so older trees still run.
- **Justified disables**: `pitloom` imports in two scripts (a release-only
  dependency, not in the lint group); `import-error` for `tests/` modules put
  on `sys.path` at run time (`tools/golden`, `tools/lists_page/measure.py`);
  `too-many-instance-attributes` on `cli_matrix.model.Cell`, a flat record
  with one field per property the judge reads.
- **CI** (`lint.yml`): `ruff check`, `ruff check --select I`,
  `ruff format --check`, `flake8` over the three directories; `pylint` runs
  apart for them, since `R0801` compares files within one run and the scripts
  repeat table shapes of `src/` and `tests/`. No ceiling could be lowered:
  `tests/test_accuracy.py` still holds the cognitive maximum.
