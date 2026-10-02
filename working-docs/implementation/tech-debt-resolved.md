---
Created: 2026-10-02
Last-Modified: 2026-10-02
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Resolved tech debt

Items resolved from
[`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md), kept
for the record: what each was, and what was done. Item numbers are the
roadmap's. Moved out of the roadmap on 2026-10-02.

- Every database lookup opened its own connection (item 29, Priority 8;
  2026-10-02), and resolving a tag value takes about five lookups: 4,000
  distinct `LicenseRef-*` tags took 9.0 s on the real database, nearly all
  in `connect` and `close`. `dbconnection.Connections` now holds the
  connection code, moved out of `database.py`. Inside
  `LicenseDatabase.reading()` a thread's queries share one connection,
  opened at the first query and closed when the outermost block ends;
  `match()`, `resolve_record()` and `diff_pair()` each run in one block.
  The same input now takes 1.85 s; the rest is two lookups that scan a
  table (item 37).
  - Rejected: a cache per value, which does not help distinct values; and
    one connection kept for the life of a `LicenseDatabase`, which sqlite3
    refuses from a second thread and which would read a deleted file
    through a stale handle (the pin in `test_db_ready.py`). The shared
    connection is per thread (`threading.local`).

- A few words of many characters cost seconds in Tier 0 (item 27,
  Priority 10; 2026-10-02): `match_short_text` scores a short input against
  every ID and name with RapidFuzz, at a cost in the input's characters. A
  200,000-character word took 2.7 s. Each scorer now gets
  `score_cutoff=threshold`, which lets RapidFuzz stop early: 0.3 s. A score
  under the threshold was dropped anyway, so no result changes
  (`test_shorttext.py::test_the_cutoff_changes_no_result`). The roadmap's 2.0 s
  in SQLite was gone by then, and a 1,000,000-character tag already took
  0.23 s.
  - Rejected: skipping the scan for a word longer than any name, the
    roadmap's direction. It is a limit on characters per word, which the
    CJK lesson of item 16 rules out, and it would change answers.

- `--json` printed internal ranking keys (item 22, Priority 12;
  2026-10-02). Each tier's own record went out as it was, with `base_score`,
  `pop_score`, `is_deprecated`, `superseded_by` and `best_window`, keys in
  build order, and a `score` on each tier's scale (a tag 1.0, an exact ID
  or name 1.0 or 1.02, a name sharing the input's words 1.01, a text match
  up to about 1.08). Now `match()` has one exit, which maps each raw record
  through `result.public_result`: the same nine keys for every result, a
  `method` (tag, field, id, name, text), an `exact` flag, the score capped
  to 0-1 and rounded to 4 places, and null where nothing was measured.
  Ranking keeps the raw score (`_match_raw`). `--json` prints JSON Lines in
  RFC 8785 form through `rfc8785`, a new dependency; the text line gains
  `METHOD=`, `EXACT=` and `SCORE=`, with an empty value for null. `--diff`
  recomputes the window (`AggregatedLicenseMatcher.diff_pair`) on the
  input Tier 2 read (a short one without its tags), since `best_window`
  stays internal. `coverage` is a length ratio and passes 1 when the input
  is longer, as it did; it is not capped.
  - The cap makes an exact hit and a look-alike both 1 (`MIT License`
    answers MIT at 1.02 and a name sharing its words at 1.01). Kept on
    purpose; `exact` tells them apart, and `--exact` keeps only exact
    results (`--threshold 1.02` never did: a close text scored up to 1.08,
    a tag 1.0). `exact` is true for a declaration, an exact name or ID (a
    deprecated row gives way to a row in use of the same name), and a whole
    input equal to the licence text after normalisation; a filled-in
    copyright line makes a text not exact, which is stricter than SPDX
    matching (item 31). A threshold outside 0-1 now exits 2. How to rank
    internally is left to item 31.
  - Decisions and paths rejected. Values are rounded to 4 places so that
    JSON and the text line agree; `-0.0` becomes `0.0`. Null, not 0 or 1,
    marks a value nothing measured: a tag, a field or an ID compares no
    text, and a name covers none. JSON Lines in RFC 8785 form print equal
    results as equal bytes and stream one result at a time. A field's exact
    hit is `method=field` with no similarity; a look-alike after it stays
    `name`. Rejected: `--threshold 1.02` as an "exact only" filter, since a
    tag scores 1.0 and a close text up to 1.08. Rejected: every deprecated
    row not exact, which made `--exact` find nothing for "GNU Affero
    General Public License v3.0" (AGPL-3.0 has a name of its own); only a
    deprecated row whose normalised name a row in use shares gives way.
    Rejected: keeping `best_window` in the result for `--diff`;
    `diff_pair` aligns again, for one licence.
- `--text GPL-2.0+` answered `GPL-2.0-only` (item 21, Priority 20;
  2026-10-01). Tier 0 matched the normalised text, which had lost the "+";
  only the CLI's bare argument tried the value as an ID first. Now
  `_try_tier0_short_text` reads a lone simple expression
  (`identifiers.is_simple_expression`) through the resolver `license_id`
  uses, so text, stdin, a file and an ID answer alike, at 1.0; a value that
  resolves to nothing goes on to the name match. The CLI's own ID-first try
  went with it. Prose spellings are item 30. Found in its review: the
  deprecated GFDL-1.1 to 1.3 had no redirect at all, so `GFDL-1.3+`
  answered `GFDL-1.3+`. They now map as the GPL family does, and
  `tests/test_deprecated_ids.py` checks every deprecated ID of the bundled
  License List that has `-only` and `-or-later` successors.
- A short input never read its `SPDX-License-Identifier` tag (item 24,
  Priority 24; 2026-10-01). Under 30 words `matcher._try_tier0_5_markers`
  read only a manifest's field (item 18), so a header line went to Tier 0
  as a license name: `SPDX-License-Identifier: MIT OR Apache-2.0` answered
  `Apache-2.0` at 1.01, and a `WITH Classpath-exception-2.0` header
  `CAL-1.0`. Now `MarkerDetector.detect_declared` reads both declarations,
  the field and the tag, at any length, and both `detect()` and it keep the
  first candidate per license through one helper (`_first_per_license`).
  The loose `License:` reader stays out of short inputs: it reads prose.
  This opened the expression parser to short inputs, whose one long token
  cost its quadratic tokenizer up to 7 s: hence the guard of item 26.
- `GPL-2.0-with-classpath-exception` was not redirected (item 25, Priority
  20; 2026-10-01). `identifiers.DEPRECATED_WITH_IDS` had six of the seven
  deprecated `-with-` IDs. Now it has all seven, and
  `tests/test_deprecated_ids.py` checks every deprecated `-with-` ID of
  the License List bundled with `py_spdx_license` against it, so the next
  one fails by name.

- A manifest's license field was lost or unflagged (item 18, Priority 16;
  2026-09-30). A TOML or INI field scored 0.95, not the 1.0 of JSON, so it
  went on to ranking and came out at 0.902 with no SPDX flags, and
  `is_spdx()` said false for `pyproject.toml` with `MIT OR Apache-2.0`. A
  Tier 0 or Tier 2 result carried no flags at all, so
  `GPL-2.0-with-GCC-exception` was not "SPDX" either. Checking it found two
  worse faults: the PEP 639 string form (`license = "MIT OR Apache-2.0"`,
  now the usual `pyproject.toml` form, and Poetry's and Cargo's) was not
  read, and no marker ran under 30 words, so a small `package.json`,
  `pyproject.toml` or `Cargo.toml` was matched by name and answered
  `Apache-1.0` at 1.01. Now:
  - the manifest readers live in `licenseid.manifest`; a JSON, TOML or INI
    field that resolves scores 1.0 and is read at any length
    (`MarkerDetector.detect_structured`);
  - the string form is read only in `[project]`, `[tool.poetry]`,
    `[package]` and `[workspace.package]` (a Cargo workspace root, which
    answered `Apache-1.0` at 1.01), so a Python `license = "MIT"` in
    `--text` is not a field, and never inside a multi-line string;
    PEP 621's table is also read written out, as `[project.license]` or
    `license.text` (a small one answered `Apache-1.0` at 1.01);
  - text with no file name is read as TOML, in either form, only if its
    first line that is not blank or a comment is a whole table header: a
    README piped in with a `[project]` example, or opening with a
    `[![badge](...)]`, answered the example's MIT at 1.0;
  - a run of white space inside a line is collapsed before `configparser`
    reads it: on Python 3.10 it scans the run once per character of the key
    before it, so 50,000 spaces after `license` took 9 s;
  - npm's old object (`{"type": ...}`) and array (`"licenses"`, joined with
    OR) forms are read; every array entry must name its license;
  - every result carries `is_spdx`, `is_osi_approved` and `is_fsf_libre`:
    Tier 2 copies them from its candidates, and Tier 0 from its cached name
    table (a lookup per result made a broad name such as `GPL`, 42 results,
    20 times slower); an expression takes them from
    `MarkerDetector.license_flags`, the rule synthetic expression candidates
    already used;
  - a manifest value must be an expression as a whole (`resolve_license_value`
    with `whole=True`): a tag's value can trail into prose, a field's cannot,
    and the MIT prefix of `MIT/Apache-2.0` dropped a license. Cargo's
    `[package]` reads the slash as OR, its old spelling. A License List
    page URL (`https://spdx.org/licenses/MIT.html`) names its license; its
    `.html` made a small manifest lose the answer `main` gave;
  - a manifest is never matched by name as a whole: a value that does not
    resolve goes to Tier 0 on its own, and only an exact ID or name counts
    (`"Apache 2.0"` is Apache-2.0; `"BSD"` would be a fuzzy 0BSD). A small
    manifest with no value, or whose value names no license, has no answer:
    `license-file` alone answered the crate name `zlib-rs` as `Zlib` at
    1.01. A reader returns None for text that is not its format, or has no
    key in it, so `[MIT]` and `["MIT"]` are no manifest and Tier 0 answers;
  - the loose `License:` reader skips a manifest, whose field the manifest
    reader has read whole;
  - the text is parsed as a manifest once per match
    (`_MatchContext.manifest`), not by each tier.

  The loose `License:` reader stays at 0.95 elsewhere: it matches prose. OSI
  and FSF flags of an OR or AND stay false by design
  (`identifiers.flag_source`). Found on the way and not fixed: items 21 to
  23.

- A blob made matching slow (item 16, Priority 15; 2026-09-30). A query of
  few words and many characters (one long token, embedded base64, a run of
  60-character tokens) went through the full RapidFuzz alignment scan on
  every candidate: 27 words plus one 2,000-character token took 5 s, and
  5,000 characters about 60 s. The scan's cost follows the query's length in
  characters, but its guards counted words: the probe is built only for
  120-499 words, and 500 words or more already fell back to
  `token_sort_ratio`. Base64 is split at `+` and `/` when normalised, so it
  arrives as many medium tokens: dropping long tokens would not have been
  enough. A first fix scored a query of more than 16 characters a word with
  `token_sort_ratio`, and review found that it lost Japanese licence text:
  Japanese is written without spaces, so a 1,570-character slice of
  CC-BY-SA-2.1-JP (104 words) fell from a certain match to 0.5. Characters
  per word says nothing about a blob. The guard now uses the probe:
  - a query of 1,500 characters or more always has a probe, cut from its
    middle by characters when it has fewer than 120 words;
  - a probe is at most 500 characters, where its own cost jumps (15 ms a
    candidate at 500, 43 ms at 600, 136 ms at 1,000); the 60 words of a
    base64 probe had been 1,900 characters;
  - the scan takes at most 6,000 characters (`similarity.alignment_affordable`,
    the one judge of it); a longer query gets `token_sort_ratio`.

  A blob fails its probe, so each candidate costs a few milliseconds; a
  Japanese slice passes it and is scanned as before. No fixture query
  reaches the character limits (at most 1,427 characters unprobed, 5,478
  probed). Trimming the 16 fixture probes longer than 500 characters, all
  Japanese or Chinese, keeps every one's top answer; only ranks two and
  three, at scores near 0.11, change. Still bounded but not free: an
  unprobed query just under 1,500 characters (a 1,000-character token)
  takes about 1 s, as on `main`, and a licence-like middle among blob
  tokens under 6,000 characters is item 11.

- A tag read with a hand-written grammar, and an ID path that read only
  `WITH` (items 15 and 17, Priorities 15 and 16; 2026-09-21).
  `MarkerDetector._RE_SPDX` wrote the SPDX grammar into a regex: it wanted a
  bare ID first, so `(MIT OR Apache-2.0)` was dropped; it wanted an ID after
  every operator, so `MIT OR (Apache-2.0 AND BSD-3-Clause)` was cut to `MIT`
  and reported as a certain match for the wrong license; and its character
  class had no `:`, so `DocumentRef-x:LicenseRef-y` was cut to
  `DocumentRef-x`. Meanwhile `matcher._try_explicit_id_match` knew a database
  row or a `<license> WITH <exception>` and nothing else, so `LicenseRef-Foo`
  and `Apache-2.0+` were no match though the same values in a tag were.
  The tag value is now the rest of its line and
  `identifiers.leading_expression` decides where the expression ends: only
  AND, OR and WITH join two parts, so a token none of them bridges ends it
  (`CAL-1.0 Licensed under ...` is `CAL-1.0`), and a dangling or unbalanced
  value is no expression at all. Comment closers need no case of their own.
  The tag branch and the explicit-ID path both resolve through the function
  JSON, TOML and INI already used (`resolve_license_value`), and
  `_match_with_expression` was deleted as redundant. An "or later" grant is
  read before the value is read as an expression, so it qualifies the ID
  beside it instead of looking like the OR operator. `:` was added to
  `identifiers._RE_TOKEN`, which silently dropped it, and an identifier now
  ends alphanumeric, so a trailing full stop is punctuation.
  Item 17 was then settled the other way round (2026-09-24): `--id` is a
  declaration of ONE license, not a second way in for expressions. It takes
  an ID, a `LicenseRef-*`, an ID with `+` and either `WITH` an exception; an
  `AND`/`OR` expression, a license name, an SPDX URL and prose exit 2
  (`option: invalid: --id: <value>; pass one license ID`), where the first
  attempt had `--id` read a tag's whole grammar and silently cut prose off
  the end (`--id "BSD-3-Clause but modified"` answered `BSD-3-Clause`).
  `identifiers.is_simple_expression` is the one judge of that rule, read by
  the CLI (`reject_compound_id`) and the matcher alike. What a *file* holds
  is unchanged: a tag and a `license` field still carry any expression.
  Three deliberate tightenings: a tag and its value must be on one line; a
  bare CLI argument is read as an ID only when it names one license and every
  part is recognised (`licenseid match "MIT or something"` no longer prints
  an invented ID at similarity 1.0000); and a 400-term chain given as an ID
  is a usage error rather than a question for the parser, which is why item
  19 now bites only on a tag. Over the 1,405 fixture files the before/after
  run differed nowhere. Left open: item 18, item 19 and the new item 20.

- An unknown SPDX tag reported as a certain match (item 6, Priority 15;
  2026-09-21). `SPDX-License-Identifier: NoSuchLicense-9.9` (or a typo such
  as `Apache-2.O`, or `Copyright`, `NONE`) made `match` return that ID with
  score 1.0 and `is_spdx: true`, while `is-spdx` said false. The tag branch
  built a placeholder candidate for any value; the JSON, TOML and INI
  `license` fields already used a stricter rule of their own
  (`MarkerDetector._synthetic_candidate`). The tag took that same function,
  so every source of an expression decides alike: a value with no
  recognised ID builds no candidate and matching
  falls through to the text tiers; a valid expression (or `LicenseRef-*`)
  with at least one recognised ID is a candidate, with `is_spdx` false if
  any part is unknown; the OSI and
  FSF flags of a `WITH` expression are its license's, as for an explicit
  `license_id`; so are those of a lone `+` ID. A `+` operator is read
  (`Apache-2.0+`), which `py_spdx_license` cannot parse, and kept in an
  explicit `Apache-2.0+ WITH X`. The same function serves the JSON, TOML and
  INI `license` fields, so they also read `+` now and give a `WITH` value its
  license's flags. The CLI's `is-*` commands used to look the top ID up in the
  database on their own, so they said false for every expression and
  `LicenseRef-*` that `match` accepted; they now call
  `AggregatedLicenseMatcher.resolve_record`, the same code as the `is_*()`
  predicates, for `--id`, a positional ID and text alike. One parser wrapper,
  `identifiers.parse_expression`, served the synthetic candidate, the `WITH`
  match and `_canonicalize_expression`, and one `WITH` lookup,
  `identifiers.with_expression_details`, the first two (items 15 and 17 later
  deleted the separate `WITH` match).
  `tests/test_spdx_tag.py` holds the table of tags and checks that the API
  and the CLI agree on each. Not done: a `NONE` or `NOASSERTION` tag reads
  as unknown (valid in SPDX documents, not licenses); the tag regex became
  item 15. "Known" for a license ID follows `py_spdx_license`'s bundled list, not
  the database, as it did for the `license` fields; a license newer than that
  list in an expression makes it `is_spdx` false.
- API `file_path` read as strict UTF-8 (item 4, Priority 16; 2026-09-21).
  `match(file_path=...)` raised `UnicodeDecodeError` on Latin-1 or UTF-16
  and matched NUL bytes and a byte order mark as text, while the CLI reads
  the same file with a Latin-1 fallback, a warning and a binary check. The
  decoder moved from `cli.py` to `licenseid.textinput`, and
  `textinput.read_text_file` is now the only place a user file becomes text,
  for the CLI and the API alike (`tests/test_textinput.py` and the parity
  test in `tests/test_option_matrix.py` keep it so). Left as they were, on
  purpose: SPDX data files (`database.py`, `spdx_source.py`) stay strict
  UTF-8, since a Latin-1 fallback there would hide a corrupt download.
  Known gaps, not part of this item: `match(text=...)` does not check for a
  NUL byte or normalise line ends as `--text` does, and an empty file
  returns no match instead of an error.
- Comment prefixes stripped twice in retrieval (item 14, Priority 10;
  checked 2026-09-21, not a defect). `retrieval.get_candidates` calls
  `strip_comment_prefixes` before `normalize_text` on purpose: the two
  regexes differ. A prefix that `normalize_text` leaves behind (`;`, `;;`,
  `///`, `**`) hides a list marker from its bullet rule, so `; 1. term`
  keeps the `1` in the query. A first random check (3,000 inputs without
  list markers) missed this; `tests/test_get_candidates.py` now pins it.
- One ranking order, and a consistent `-only` / `-or-later` tie-breaker (item
  8, Priority 12; widened on 2026-09-20 to the whole tie-breaker). Three sorts
  in `matcher.py` had drifted apart: the main ranking took `DEP_PENALTY` off
  a deprecated ID, the tie-breaker's re-sort did not (so it could put a
  deprecated ID back above its replacement), and `match_short_text` carried
  keys its results never have. All three now use `ranking.ranking_key`, or (short
  text) `(-score, license_id)`. Three more inconsistencies in the tie-breaker:
  its 0.01 window was decided by the last bit of a float (`0.91 - 0.90` is not
  a tie, `0.35 - 0.34` is), now compared after rounding to 9 places and named
  `TIE_WINDOW` (in `ranking.py`); and three readers of "or later" disagreed.
  The tie-breaker,
  the bare-ID prose path (`identifiers`) and the marker detector (`markers`)
  each had a regex of their own, so `version 2 of the License, or any later
  version` came out `-only` from the marker detector and `-or-later` from
  Tier 0. They
  now share `classify.OR_LATER_PHRASE` (with a `not`/`no` guard), and
  `tests/test_match_ordering.py` pins that both paths read every phrase alike.
  Measured with a before/after run over the fixtures plus 160 synthetic
  headers (4,741 results): 344 changed. 184 are fixture results; 182 of them
  are GFDL slices or distorted copies that moved from `-only` to `-or-later`
  (the GNU Free Documentation License's own text says "or any later
  version", and the `-only` and `-or-later` variants have identical bodies),
  and 2 differ only at rank 5. The other 160 are synthetic headers; 32 of
  them changed their top answer, all `-only` to `-or-later`, for `or newer`.
  Of the 3,249 license-text results (both popularity settings), 1,949 had the
  right top answer before and 1,948 after (30 GFDL `-only` rows lost it, 29
  `-or-later` rows gained it).
  The GPL family already behaved this way.
  Left open: the tie-breaker is applied once per `match()` and is not
  idempotent (a second pass on a pair whose preferred side started below its
  peer nudges it again); the +/-0.005 nudge is kept on purpose, so results stay
  sorted by score, at the price of moving reported scores by up to 0.005 and
  letting a pair member pass an unrelated license within that; the name-based
  reader in `markers.MarkerDetector._name_variants` (`or any version later`)
  is a fourth regex that is not shared; `is_pure_license_text` does not flag
  slices of a license, so a quoted notice in one still counts as a grant.

- `match()` silently ignored unknown options (item 1, Priority 20):
  `AggregatedLicenseMatcher.match()` now raises
  `InvalidInputError('option: invalid: <names>; use one of ...')` for a key
  outside `MatchRequest` (a typo, or a removed option such as `enable_java`),
  before it looks at any input, so an explicit `license_id`, empty text or an
  unreadable file cannot let one through. The names are sorted, so the message
  is stable. The `is_*` predicates already refused an unknown keyword, with the
  interpreter's `TypeError` rather than this message; that difference is left.
  Left open: a *known* option is still ignored when `match()` returns before
  ranking (an explicit `license_id`, a bare ID or name, an
  `SPDX-License-Identifier` tag), so `match(license_id="MIT", exclude=["MIT"])`
  returns `MIT`. See item 5. Tests: `tests/test_match_options.py`.

- `py-spdx-license` upper bound (item 3, Priority 16): the requirement is
  now `py-spdx-license>=0.0.1,<0.1`. Version 0.0.1 is a single release with
  no type information, so a 0.0.x API can change without notice; only
  `markers.py` imports it. Raise the bound by hand after checking the new
  release against `tests/test_markers*.py`.

- Unready database answers silently (2026-09-19 audit): after a failed first
  `update`, `match` said "no license found" and `is-osi` printed `false`
  (exit 1); a non-SQLite `--db` or a directory crashed with a traceback; and
  a read command on a 0-byte file wrote tables into it. Now `match`, the
  `is-*` commands and `AggregatedLicenseMatcher()` check readiness first, read
  only, and report `database: not found`, `empty`, `invalid` (another
  program's objects beside an incomplete set of ours, or a `licenses` table
  without our columns; no `update` hint, as it would write into the file) or
  `unreadable` with exit 2 (`DatabaseNotReadyError`). Ready means the
  `licenses`, `db_metadata` and `license_index` (FTS5) tables exist,
  `license_list_version` is not blank, every `license_id` is text, and
  `licenses` and `license_index` each have a row. The check reads with plain
  `mode=ro`: `immutable=1` was tried and dropped, because every database
  licenseid writes is in WAL mode and immutable turns locking off, so a read
  during an `update` could see a torn file.
  The check is structural, not `PRAGMA quick_check` (about 200 ms on a real
  database, twice per command): damaged pages that keep the schema and the
  first rows plausible can still give a wrong answer. A fuzz run found only
  page swaps of the `licenses` root page (exit 1 or a traceback before the
  `typeof` probe, `NOT INDEXED` and exact column names were added).
  A table of ours whose schema is not ours is `invalid` too: the table names
  are common enough (`licenses`, `db_metadata`) that a seat inventory or an
  asset register hits them, and calling such a file `empty` used to send the
  user to `update`, which wrote licenseid's schema into it.
  Same change: `get_default_db_path()` no longer creates the directory (only
  `update` does) and `--clear-cache` works on the path without opening the
  database, so read commands no longer crash on an unwritable `HOME` and a
  corrupt database can be cleared. Because they write or delete, `update` and
  `--clear-cache` call `reject_foreign_database` first (it runs inside
  `LicenseDatabase.clear_cache`, so the Python API refuses what the CLI
  refuses). It refuses an `invalid` database, anything that is not a regular
  file with the SQLite header, a path naming no file, a file it may not read,
  and an `unknown` one; it accepts every other condition, which is what those
  commands are for. Gate and guard resolve one file the same way through every
  spelling of it, by path (`licenses.db`, `licenses.db/`, `licenses.db/.`) and
  by URI (`file:`, `file://`, `file://localhost`, `?vfs=`), and refuse
  anything that is not a regular file or a directory: a named pipe would have
  held the read-only open for ever. Only `mode=memory` and the exact base
  `file::memory:` are memory; `file::memory:notes` names a file on disk.
  Reading is the opposite way round: an `unknown` database
  is not refused, because a wrong refusal costs the user an answer they could
  have had.
  Left open: the metadata is committed before the fingerprints are computed,
  so a kill in between leaves a "ready" database without fingerprints. That
  is not merely a degraded answer — measured on a real database, the top
  match changes (`MIT` becomes `Xnet` for MIT text), so the command reports a
  different license with no warning. Fix by writing the metadata in the
  fingerprint transaction, or by adding a fingerprint row to the readiness
  check. A `sqlite3` failure after the check exits 2 on the CLI
  (`database: unreadable`); the API keeps raising the raw error (item 10).

- `cli.py` test coverage (2026-09-19 audit, Priority 18): was 66-75%. Now
  100% of lines and branches, from `tests/test_cli_errors.py`,
  `tests/test_cli_input.py`, `tests/test_cli_output.py` and the combination
  matrix `tests/test_option_matrix.py`.
- Tier 3 Java path (2026-09-19 audit, Priority 15): untested and silent on
  failure, so removed instead of fixed. The optional `tools-java` tier
  (`--java`, the `licenseid[java]` extra, `SPDX_TOOLS_JAR`) was off by
  default and not tested in CI; removed on 2026-09-19 (see `CHANGELOG.md`).
- Library diagnostics on standard output (2026-09-19 audit, Priority 16
  after re-scoring): progress, the `Data sources:` report and warnings from
  `licenseid update` and `--clear-cache` now go to standard error through
  `licenseid.console` (`status`, `warn`, `error`); standard output carries
  only the result line. Error and warning texts were rewritten to one
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]` grammar (see `AGENTS.md`),
  guarded by `tests/conftest.py::check_diagnostic_grammar`. Drive-by: the
  license-preparation progress line wrongly said `Preparing exception
  data...`.
- Type-1 `id_casing` and `id_deprecated` accuracy gaps — implemented; see
  the status note at the top of
  [`../design/optimization-recommendation.md`](../design/optimization-recommendation.md).
- `matcher.py`/`database.py` complexity and file size — tracked
  separately now in
  [`../design/complexity-and-file-size-roadmap.md`](../design/complexity-and-file-size-roadmap.md)
  rather than here, since it has its own linter-enforced ratchet.
- Stale `docs/implementation/` navigation (no current-state entry point)
  — fixed by `working-docs/implementation/README.md`.
- `requests` dependency floor, stale benchmark plan docs — resolved.
- CI guard rails (2026-09-19 audit, phase 0): the type check ran with
  `--no-strict-optional` and `continue-on-error`, so it never failed a build; CI
  ran neither `flake8` nor `pylint tests/`. Now `mypy` (strict, `src/` and
  `tests/`, from `[tool.mypy] files`) blocks, `lint.yml` runs `pylint` and
  `flake8` on `src/` and `tests/`. Tests stay on Python 3.10 and 3.14 only, to
  save CI resources. Same pass: removed a stdout debug line from the `--java`
  path, the unused `debug_gpl.db`, a `working-docs/` link and a wrong PR link in
  `CHANGELOG.md`; added `codemeta.json`, now the source that `codemeta2cff.yml`
  generates `CITATION.cff` from.
