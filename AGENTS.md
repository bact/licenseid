# Agent instructions

Each rule is binding. Rationale and history live in `working-docs/`
(internal notes; user-facing docs never link into it: cite a PR or issue).
`CLAUDE.md`, `GEMINI.md` and `.github/copilot-instructions.md` are symlinks
to this file: edit `AGENTS.md`.

## Project

- `licenseid` detects licence IDs by hybrid search: Tier 0 short text (IDs,
  names), Tier 1 recall (SQLite FTS5 trigram), Tier 2 precision (RapidFuzz).
  `resolve()` reads a declared licence value as an SPDX expression.
- Private alpha, one developer. No backward compatibility needed yet.
- Build: `hatchling`, PEP 621 `pyproject.toml`.
- `update` takes a release from one of three sources: `compact` (our 1.3 MB
  bundle on the `data` branch), `upstream` (SPDX's tarball), `packaged` (the
  bundle in the wheel). "Bundle" names only the file format (`spdxdata`,
  `spdx-bundle*.json.gz`); say `compact` or `packaged` for a source. Terms:
  `working-docs/implementation/data-fetching-and-caching.md`.
- Which values `resolve()` should read next: measure, do not guess
  (`tools/pypi_licence_sample/README.md`; findings in
  `working-docs/design/resolver-0-7-evidence.md`).
- Precision over recall: no answer beats a doubtful guess. Before a refusal,
  measure what it loses (real values or List windows, base against branch).

### Where things are

- `working-docs/design/`: plans and sketches, not built, may be discarded.
  `working-docs/implementation/`: what was built, why, paths rejected; start at
  its `README.md`. Releasing: `release-process.md` there (gates compare with the
  last tag, not only `main`). `working-docs/paper-notes/`: sourced material for
  a paper; add publishable findings; start at its `README.md`. Every
  `working-docs/` file has `Created` and `Last-Modified` (`YYYY-MM-DD`) in its
  front matter, no date in the file name.
- User docs: `README.md` (short; the PyPI long description and the Citation
  block, so its links are absolute) and `docs/`: `installation`, `cli`
  (commands, options, exit codes, predicates), `output` (text record, JSON,
  escaping, error lines), `python-api`, `resolve` (every field of
  `resolve()`'s result, categories, trust, refusal reasons, quote marks),
  `how-it-works`, `development`. Detail goes in `docs/`, not the README. A
  change to any of `resolve()`'s fields, categories, trust, refusal reasons
  or quote marks updates `docs/resolve.md`
  (`tests/test_resolver_shapes.py` checks its category table).
- `docs/lists.md` is GENERATED, never edited by hand: the lists `resolve()`
  reads (`ALIASES`, `TITLES`, `TROVE_NAMES`, the `resolveurl` and
  `resolveslash` tables, `VERSIONED_NAMES`) and the named rules (T1 to T3, P1
  to P3), each table read from its code object and each rule linked to its
  function. `python -m tools.lists_page` writes it (`--check` tests it);
  `tests/test_lists_page.py` fails when the page and the code differ. A new
  or changed row, list or named rule: change the code, add its source to
  `tools/lists_page/evidence.py` (a rule: `rules.py`), run the command. What
  can be measured (the PyPI counts, the answer and `EXACT` of an example) is
  computed, never typed. A new list gets its section in
  `tools/lists_page/render.py`, its `CATEGORY` and `EXACT` value.
- User docs are tested: `docs.yml` runs these tests and `markdownlint-cli2
  "**/*.md"` on a Markdown change, which the other workflows skip.
  `test_docs_vocabulary`: each option, step kind, detail, reason, result key
  (`test_docs_numbers`: number) is in its page; links and anchors resolve.
  `test_docs_status`: line numbers and releases only on `PINNED` pages; a
  time-bound sentence (`yet`, an upstream link) is in `TIME_BOUND`, reread
  for each version; one version everywhere. `test_docs_examples`: a block
  that shows a result runs (`$ licenseid`, `licenseid ...  # result`, Python,
  `resolve()` JSON, resolve-flow's worked examples), else is marked
  `<!-- docs-example: skip: <why> -->`, or `run: <command>; head` for an
  output block; `COUNTS` holds the blocks of each page. Review habits:
  `working-docs/implementation/release-process.md`.
- Test fixtures: `tests/fixtures/README.md`.

### Modules (`src/licenseid/`)

Keep `detector.py` under 800 lines: logic that needs no detector state goes
in another module.

- Detection: `detector` (the pipeline), `keptdetector` (`licenseid.detect()`,
  one detector per default database), `detectrequest` (checks of a call needing
  no database), `resolvefirst` (input `resolve()` reads whole; the cut of a
  short refused one), `shorttext` (Tier 0), `namehits` (which name hits of Tier
  0 stand: tied names) and `namerules` (what beside one name doubts it),
  `retrieval` (Tier 1), `textcorpus` (word codes), `textlocate` (5-gram votes,
  windows, count limits), `wholetexts` (key, overlap, look-alike doubt),
  `firsttext` (1st text), `textnames`, `ftsquery` (its `MATCH` string: 20 words,
  each cut to 128 characters), `idoptions` (`exclude`, `hint`: API only, free
  text only, case-folded, a bare deprecated ID stands for both twins, kept under
  `as-written`), `variants` and `variantstated` (the `variant` option: what a
  bare ID and a text answer, `variant_stated`, a trailing "only"), `similarity`
  (Tier 2 scores of the candidates, the fingerprint bonus; a long input against
  a licence's core too, the higher kept, coverage over the text that won) with
  `coretext` (a template without its optional parts), `fingerprint` (maths) and
  `fingerprintstore` (its table), `ranking` (sort order, `-only`/`-or-later`
  tie-breaker), `markers` and `candidates` (its helpers), `classify` (prose "or
  later"), `grantsubject` (whose grant), `identifiers`, `normalize`, `result`
  (public result, JSON and text lines), `types`.
- Reading an ID: `looseid` ("Apache2", "GPLv3"; `disambiguate_whole`),
  `bsdclauses` (BSD-N-Clause by its conditions), `deprecatedids`,
  `plusoperator`, `versionkey` (a bare major the List has another minor of names
  no row, `ambiguous_ids`; an "or later" grant exempts it), `quotes` (quote
  marks around a whole value, `「」` too), `dropguard` (what a loose reading must
  not drop), `hiddenchars` (control and format characters off the ends and
  beside white space, inside quotes too), `grantchain` (a tag whose grant an
  operator follows, read by `resolve()`).
- Resolver: `resolver` (value to expression and steps; types in
  `resolvertypes`), `resolveleaf` (one licence), `resolvecompound`,
  `resolvesemicolon` (`;`: listed, no operator), `resolveslash`,
  `resolvetrove` with `trovenames` (data), `resolveprose` (`BSD 3-Clause
  License`), `resolvetitle` and `resolvealias` (data, read through
  `resolvetable`), `resolveurl` with `nugetpath` and `urlkey` (standard
  library and `listlookup.fold_case` only),
  `ruleread` (whether a rewrite rule read a value, for the `EXACT` of a tag
  or field), `resolvereason` (refusal no reader explained), `resolverinfo`
  (resolver, parser and list blocks; a detection's `lists`), `exprcanon`,
  `exprtokens`, `exprflags` (OSI, FSF, List flags; `judged_id`).
- Lists: `listlookup` (a Protocol; `fold_case`), `listindex` (the shipped
  bundle in memory), `listsource` (database or packaged), `listrules`
  (entries kept, deprecated targets).
- Data: `database`, `dbconnection`, `dbcache`, `dbschema`, `dbcheck`, `datadir`,
  `records` (rows), `spdxdata` (a release as data; no `requests`, `click` or
  `rapidfuzz`), `releasesource`, `spdx_source`, `textinput` (bytes to text),
  `manifest` (the `license` field of package.json, pyproject.toml, Cargo.toml,
  setup.cfg; a TOML basic string decoded, a literal one not).
- CLI: `cli` (group, `main`), `cliinput` (one of file, value, `--text`, `--id`,
  `-`), `clidetect` (`detect`, `is-*`), `cliupdate` (`update`, `clear-cache`),
  `cliresolve`, `clicommon`, `output`, `console`, `usage`, `errors`, `warning`.

## SPDX matching

- Follow the SPDX matching guidelines and templates (normative):
  <https://spdx.github.io/spdx-spec/v3.0/annexes/license-matching-guidelines-and-templates/>
- Text transformations are order-sensitive. Document each step in the code
  with its rationale and reference.

## CLI output

Unix philosophy: consistent, predictable, parseable; works with `awk`, `wc`,
`xargs`. `tests/test_output_pattern.py` runs every command (text with `-v`,
and `--json`) against these rules and checks the default output against the
`-v` record.

### Results (standard output)

- Standard output carries only the result, written by `output.echo` or
  `output.echo_json`; never `print`, `click.echo` or `json.dumps`.
- `detect` and `resolve` print the expression alone: one line per result
  (`--top N` in rank order), an empty line for none. `-v`/`--verbose` prints
  the record. `--json` always prints the full object (`-v` beside it is a
  no-op). `is-*`, `update`, `clear-cache` take no `-v`. `-V` is
  `--version`. `--id-only` is gone.
- The record: one record per line. The first key names its kind (`EXPRESSION`
  the answer, first; `STEP`, `REASON`, `OPERAND`, `LIST`, `STATUS`). No answer
  still prints the record, every field empty but `REASON` and `TEXTS`.
  `detect`'s last fields: `SAME_TEXT` (after `VARIANT_STATED`) is empty unless a
  text answer shares its normalised text with other List IDs (`detector` passes
  `result.public_result` the `twins` it builds from `database.text_parts`, minus
  the final expression); `REASON` (CLI only, not in `types.Detection`) is empty
  on an answer, else `below threshold`, `not exact`, `several texts` or `no
  match` (`clidetect._no_answer_reason`); `TEXTS` last, in file order
  (`firsttext`'s search; no answer: the top candidate's, else `texts()`), a
  field, not a kind.
- Fields: `KEY=VALUE`, upper-case key, no spaces round `=`, one tab between
  fields (`result.fields_line`); a key ends at the first `=`. Fields are only
  appended at the end: never removed, renamed or reordered.
- Escaping (`result.text_field`, read back by `result.read_text_field`):
  tab, CR, LF, backslash as `\t`, `\r`, `\n`, `\\`; a character the stream
  cannot encode as `\xHH`, `\uHHHH`, `\UHHHHHHHH` (`output.echo`).
- Nothing is an empty value. A flag is `true`, `false`, or empty when there
  is nothing to judge: never a false `false`. In the API, None is nothing,
  never `""`.
- `--json` and every JSON the CLI writes: one RFC 8785 (JCS) object per line,
  only through `result.json_line` (never `json.dumps` on an output path), as
  UTF-8 bytes on every locale. Each text key appears in lower case, a flag is a
  boolean, and `null` exactly where text is empty. JSON may hold more (`resolve
  --json` the whole resolution, `detect --json` the flags and `lists`); an added
  key is `null` when empty. The text-to-JSON key map of `resolve` (`STEP` to
  `steps[].kind` and `expansions[].kind`, `OPERAND` to `operands[].text`) is in
  `docs/resolve.md`.
- `detect`'s `lists` (`Detection.lists`) come from `resolverinfo.list_info`, the
  builder of `resolve()`'s `lists`: never a second copy. Its JSON (`json_line`)
  and text line (`result.text_line`) print the public form
  `result.public_result` builds at the one exit of `detect()`: tiers rank on the
  raw score (above 1 for a Tier 0 hit, look-alikes too, and a close text with
  bonuses), never on the public one, which is capped to 1. `exact` tells results
  at 1 apart; set it where a result is made.
- Only exceptions to the pattern: the default output of `detect` and
  `resolve`, `--version` (`licenseid <version>`), `--help`.

### Exit codes

- 0: an answer, yes, done. 1: no answer, no, or a failed action (`update`, a
  delete `clear-cache` could not make). 2: usage error (two inputs, `--json`
  with `--diff`), unusable input, database not ready, or a result that could not
  be written (`output: write failed: <reason>`). 141: the reader closed the
  pipe. 130: Ctrl-C, also while options are parsed (`cli.main()` runs click
  outside standalone mode). 141 and 130 print nothing (`DatabaseErrorGroup`).
- Exit 1 of `detect` and `resolve` prints no `ERROR` line: "no" is an
  answer. `update` and `clear-cache` print no record on exit 1, only their
  `ERROR` line. A `WARNING` about input or database (`variant not stated`,
  `N days old`) may come with any outcome.
- A closed standard input is no input. A failing standard error is pointed
  at the null device (else the flush at exit turns every status into 120).

### Diagnostics (standard error)

- Through `licenseid.console` (`status`, `warn`, `error`), never `print` or
  `click.echo`. `console.emit` is the one writer of both streams: bytes under
  the text stream, so every line ends in `\n` on every platform (Windows `\r\n`
  breaks `awk` in Git Bash), in the stream's encoding with backslash escapes
  (UTF-8 for `--json`). Tests simulate Windows with `TextIOWrapper(...,
  newline="\r\n")` (`tests/test_output_encoding.py`).
- One event per line: `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`. No
  trailing period, no "Please", no sentences.
  `tests/conftest.py::check_diagnostic_grammar` fails a test that prints a
  line, or gives a `LicenseIdWarning`, off this grammar.
  - `LEVEL`: `ERROR` (command fails, non-zero exit) or `WARNING` (a
    fallback lets it continue).
  - `SUBJECT`: lower-case word or cache file name: `command`, `database`,
    `directory` (the default data directory), `input`, `option`, `output`,
    `usage`, `version`, `cache` (a cache file with no plain name),
    `latest.json`, `licenses.json`, `popularity.csv`,
    `spdx-bundle-v<ver>.json.gz`, `spdx-bundle.json.gz` (packaged),
    `spdx-data-v<ver>.tar.gz`.
  - `CONDITION`: short lower-case fragment, reused across subjects. The full set
    (add new ones here): `not found`, `invalid`, `missing`, `empty`,
    `unreadable`, `binary file`, `not UTF-8, read as Latin-1`, `N days old`,
    `normalization vN outdated`, `build vN outdated`, `build vN newer`,
    `download failed`, `cache read failed`, `cache write failed`,
    `cache unusable`, `download unusable`, `stale cache unusable`,
    `parse failed`, `variant not stated`, `deprecated ID`,
    `N rows with missing or non-numeric num_pushers`, `update failed`,
    `delete failed`, `write failed`, `compact failed`,
    `older than the database`, `too few words for text`, `overridden by input`.
  - `DETAIL`: one line. A path through `errors.shown` (control characters
    escaped, `;` as `,`), a value through `errors.one_line` (folded, cut to
    60), an exception through `errors.typed`. Not result escaping: a
    backslash stays, so a Windows path reads as typed.
  - `ACTION`: the fallback taken (`using stale cache`, `using stale <file>`,
    `downloading`, `downloading <file>`, `using cached <file>`,
    `using packaged data v<ver>`, `counted as 0`, `using A, B`,
    `using <answer>`) or the command to run (`run 'licenseid update'`), on
    the same line as its cause.
- Raise a failure as `licenseid.errors.LicenseIdError` (`SUBJECT: CONDITION…`,
  no prefix): the CLI prints it after `ERROR:` and exits 1, or 2 for
  `InvalidInputError`. `DatabaseNotReadyError` (missing, empty, invalid,
  unreadable) exits 2 in `detect`, `resolve`, `is-*`. `update` and `clear-cache`
  refuse only an `invalid` database (not built by licenseid) or an `unreadable`
  symlink loop: they exist to fix the rest. Any other exception in `update`,
  RuntimeError subclasses such as RecursionError included, becomes
  `SUBJECT: update failed: <Type>: <text>`. A default directory `update` cannot
  make is `directory: write failed: <dir>: <reason>; pass --db`.
- A step printing partial progress (`status(..., end="")`) that can fail
  calls `console.end_line()` in a `finally`.
- click's usage errors use the grammar too
  (`ERROR: option: not found: --jsn; did you mean --json`): `usage.py`
  re-raises them as `UsageLineError` in `parse_args` (option callbacks
  included) and in the group's `invoke` (unknown command, `BadParameter`).
  Wrap a command run outside the group too. No subcommand: help to standard
  error, exit 2, through `console.write`. `--help` and `--version` go
  through `echo` (`output.EchoHelpCommand`).
- Library code never writes a warning: it gives a `LicenseIdWarning`
  through `warning.warn` (attributed to the caller; `warning.once()` for
  once per process). The CLI prints each as a `WARNING:` line through
  `console.warn` (`clicommon.printed_warnings`, entered in
  `DatabaseErrorGroup.main`), in order, never deduplicated (filter
  `always`); other warnings are left to Python. Only the CLI's own warnings
  (`N days old`) call `console.warn` directly. Exception: the progress of
  `update` and `clear-cache` (`console.status`) comes from the library.
- Tests: a library call's warning is asserted with the `given` fixture or
  `pytest.warns`; a step of `update` called alone uses the `printed`
  fixture. An unrecorded `LicenseIdWarning` is a test error
  (`filterwarnings` in `pyproject.toml`).

## Reading input

- One reader for user input: `textinput.read_text_file` / `decode_input`
  (UTF-8, BOM dropped, else Latin-1 with a warning; NUL means binary,
  `reject_binary`, which `--text` also calls). Never `open()` a user file
  elsewhere (`tests/test_textinput.py` checks `cli*.py` and `detector.py`).
  `--text` is taken as written: no escape decoded. SPDX data files stay
  strict UTF-8 (a fallback would hide a corrupt download).
- A lone surrogate (API string, invalid UTF-8 argument) cannot bind to
  SQLite: `textinput.reject_lone_surrogate` raises `InvalidInputError` where
  the detector takes a text; `clicommon.reject_unencodable` exits 2 first
  for `--text` and the argument.
- Input with no extension starting `[` or `{` is tried as JSON, then TOML/INI.
  Every licence value (tag, JSON, TOML, INI, explicit `license_id`) resolves
  through `MarkerDetector.resolve_license_value`, and every expression through
  `_synthetic_candidate`: a candidate only for a valid expression or
  `LicenseRef-*` with at least one recognised ID. `is_*()` and `is-*` answer
  from `LicenseDetector._resolve_record`; never look a record up on the side.
- A whole input (argument, `--text`, stdin, file, `detect(text=...)`) is
  read by `resolve()` first (`resolvefirst.as_resolved`): its expression,
  compound too, is the answer. The rest goes through the tiers. One under
  `resolvefirst.MIN_TEXT_WORDS` (10) words that the name tier does not
  answer gets no text match and warns `too few words for text` (not after a
  tag was taken out; also where `namehits` dropped the hit). Han and kana
  text is never cut by word count.
- `--id` and `detect(license_id=...)` declare ONE licence, judged only by
  `identifiers.is_simple_expression` (an ID, `+` unless `-only`/`-or-later`, or
  `LicenseRef-*` without `+`; optionally `WITH` an exception, any brackets).
  `cliinput.reject_compound_id` exits 2 (`errors.invalid_id_error`);
  `LicenseDetector._try_explicit_id_match` raises, so ask the predicate first.
  Never widen `--id` to expressions. The CLI makes no ID guess of its own.
- `exclude` and `hint` are `detect()` API options only (no CLI flag;
  `resolve()` has neither) and act on free text only: a declaration (tag,
  field, `license_id`, a whole input `resolve()` reads) is never filtered or
  hinted. Upgrade their bare deprecated IDs once per call
  (`idoptions.upgraded_options`, warning `deprecated ID`).
- `variant` (`--variant auto|as-written|only|or-later`, API `variant=`,
  `licenseid.variants`): under `auto` a declared value stays as written
  (bare `GPL-2.0`, `-with-` IDs); under `auto`, `only` and `or-later` a text
  or name match never answers a deprecated ID (`variants.settle_text`:
  `-or-later` first where `ranking.or_later_signal` finds a grant of that
  licence, else `-only` first, also for an `-or-later` top no grant chose
  whose ID is unwritten); `as-written` leaves a text's twins as the bare ID.
  `only` and `or-later` decide declared values too (`variants.fallback`, a
  context variable `variants.read_as` sets in `LicenseDetector._match_raw`;
  outside `detect()` it reads `only`). Stated words win, with `option:
  overridden by input`. Both warnings are only for a printed result
  (`variants.output_bar`: `--threshold`, `--exact`, `--top`; 0.85 in the
  API); a text's guess only at `variants.ANSWER_SCORE` or more.
- Every result carries `evidence` (the value as written, or a text's signals),
  set where a result is made (`variants.read_from`, `settle_text`), never a
  flag. A reader that decides a form (`looseid.read_inexactly`, `mark_guessed`)
  marks it in `evidence.decided`: a decided form is never stated, whatever
  another operand says (`identifiers` merges equal operands, so no count can).
  The one reader `variants.stated_of` gives the record field `VARIANT_STATED`,
  fail closed (no evidence, no word: false); `result.public_result` applies the
  one rule that a variant licenseid chose (`guessed_of`) is not exact. `is-*`
  lines have no `VARIANT_STATED`; `is-osi`/`is-fsf` judge a kept deprecated ID
  by its `-only` twin (`exprflags.judged_id`).

### Expression readers (one reader each; do not write another)

- Tag value: the rest of its line up to the next tag (`[ \t]`, never `\s`).
  `identifiers.leading_expression` decides where the expression ends: only
  AND, OR, WITH join parts, only white space between them; a token none of
  them bridges ends it; a dangling or unbalanced value is none. Never write
  the SPDX grammar as a regex; comment closers need no case of their own.
  A dash or `_` run touching its end, then the end of the value, white
  space, `.`, `,` or `+`, cuts it: no expression (`dropguard.cut_by_joiners`).
- "Or later" grant: `classify.OR_LATER_PHRASE` is the one phrase reader
  (imported by `grantsubject`, `identifiers.disambiguate_deprecated_id`,
  `markers`, `looseid`); `classify.grant_end` finds a grant and its end;
  `classify.grant_head` is the one rule for the gap between ID and grant (a dash
  between words, or ONE dash or `_` glued to the ID, is a separator; a glued run
  of two or more is dropped characters), followed by `before_grant` and the
  tag's `dash_gap`. The grant qualifies the licence beside it
  (`identifiers.qualify_trailing_grant`): `MIT OR GPL-2.0 or later` is
  `GPL-2.0-or-later OR MIT`; with WITH it belongs to the licence. A version
  number between ID and phrase (a number the phrase starts with counts too,
  unless it is the ID's own version) means another licence's grant. A grant ends
  the expression: `resolve()` refuses anything after it but an operator chain
  (`MIT or later AND ISC`), which a tag hands to it (`grantchain.chain_read`).
  `grantsubject.grants` is the one reader of whose grant a phrase is (a version
  after a licence's name, `version`, `v` or `the License`; `Python 3.8 or later`
  is a tool's): `ranking.or_later_signal` and `only_signal` ask it per licence;
  a phrase it cannot own (`has_unowned_phrase`) counts as a grant for the
  tie-breaker and leaves `settle_text`'s `-only` alone (`ranking.leave_signal`,
  as does a pure licence text). `looseid.declared_grant_id_text` only finds
  where a grant starts (bare "or later" read as after a number unless
  `classify.is_negated`). Add a phrasing to `classify.OR_LATER_PHRASE` and to
  `PHRASES` in `tests/ordering_helpers.py` (`test_match_ordering` and
  `test_resolver_shapes` hold every reader to it).
- Ranking and the tie-breaker sort with `ranking.ranking_key`; short-text
  results sort by `(-score, license_id)`.
- Tag and `license` field answer only with List operands or `LicenseRef-*` (`MIT
  OR Apache 2.0`: no answer). `MIT or later` is `MIT+`. No licence for: a
  detached "+", a mark `resolve()` drops before "or later" (`MIT; or later`), a
  licence right after a mark (`MIT/Apache-2.0`) or after a grant (`GPL-2.0 or
  later, ISC`; `looseid.lists_another`, `lists_after_grant`, whose item rule
  `_lists_another` shares), an "only" after an operand of a list (`MIT OR
  GPL-2.0 only`: `variants.qualify_trailing_only`). A mark glued to a grant's
  end (`or later-`, `?`) is refused by `looseid.disambiguate_whole`
  (`dropguard.glued_marks`) as by `resolve()`. So is a run of end marks
  (`or later..`, `or later.;`; `dropguard.grant_end_marks`, one reader for
  `resolveleaf._single`, `disambiguate_whole` and a whole field in
  `looseid.drops_words`); a tag still reads it
  (`tests/test_grant_glued_marks.py`). Keywords match in ASCII case only
  (`(?a:...)` or `re.ASCII`; `tests/test_readers_case.py`).
- "+": `plusoperator.PLUS_OPERATOR` (`strip_plus_operator`,
  `replace_plus_operator`, `plus_after_qualifier`; standard library only) is the
  one reader: right after an ID, never after a space, a "+", an exception or a
  `LicenseRef-*`. `versionkey.version_key`, `is_simple_expression` and
  `classify`'s shorthand ("GPLv2+") follow it; `tests/test_plus_readers.py`
  holds all four to one table: change one, run it. `normalize_text` drops a "+"
  that is no operator, so `detector._try_tier0_short_text` returns None for a
  value under 30 words that `resolve()` refuses with a "+" reason
  (`resolvereason.is_plus_refusal`; add new reasons to its constants).
- Marks: a lone bracket or slash at an end (`(MIT`, `MIT)`, `/MIT`, `MIT/`) is
  refused, a lone quote read (`tests/test_stray_marks.py`); a reference keeps
  its trailing `-`/`.` in every channel (`exprtokens.expression_tokens`).
- Cut ID: a bare major (the last number all digits) whose key has a sibling
  minor on the List names no row (`versionkey.ambiguous_ids`: `loose_id`
  gives None, `resolveleaf._base` raises `_Ambiguous`, reason `version
  ambiguous: <IDs>`, in `resolvereason._NO_TEXT_CONDITIONS`). Where a
  grant was read off the text (`_plus`, `_single`) `_base(granted=True)`
  exempts it. A run of `-`/`_` joined to the end of a loose ID is a dropped
  character (`dropguard.trailing_joiners`; on a head before a grant only a run
  of two or more: `least=2`).
- Tier 0 asks `resolve()` first for a value under 30 words: what it reads
  is the answer; what it refuses is matched as before, except after a
  dropped mark or an unpaired bracket, or (under 10 words only) a "+" that
  ends or starts a word or stands alone in marks (`MIT++`, `GPL-2.0 (+)`;
  not `C++`): `resolvereason.refuses_text_match`.
- Token set reads a name held whole in an input as the input's name:
  `namehits.settle` drops that hit where the rest of the input names something
  else. Of tied names (`namehits`) the one written whole (its words in order,
  one word between at most) beats one made of scattered words; of those the
  longest of nested names wins, two licences give none. `namerules` judges the
  words that touch the name, never the whole input: a cut version (own grants,
  `grantsubject`, on an `-or-later` or `+` ID exempt one number; a whole version
  counts near the name only); a GPL hit if every "General Public" follows
  `Lesser`, `Library` or `Affero`; `with` within three words after the name,
  then an exception of the List of two words or more, or "exception" within five
  words (one word such as `GCC` is no exception); a fragment of a longer name;
  another ID written whole (joined to the name by a comma, slash, "and" or "or";
  an acronym only so); a dash glued to a word of the name. A second licence
  whose name lacks the `v` of its version, or its grant, is another name too
  (`namehits._without_grant`). Generic words
  (`namerules.GENERIC`) are no evidence. A dropped hit that scored above 1 is
  final from 10 words on (no Tier 1; under 10 words `too_short` warns); below 1,
  Tier 1 runs. Mixed-content sections (`match_short_text`) only lose the hit.
  Add a rule there, with a made-up row in `tests/test_namehits.py`.
- "/" is OR only in a whole value (`resolveslash.slash_parts`): each piece an
  exact-case List ID (a "+" read by `plusoperator`) or `LicenseRef-*`, at least
  one List ID; never a tag, never inside a `;` part. `MIT/X11` is in
  `REFUSED_PAIRS`. `tests/slash_pins.py` pins 0.8.3's answers: moving one is a
  loosening.
- Licence URL: one key, `urlkey.url_key` (ASCII only; scheme, `www.`, fragment,
  trailing `/`, one page suffix dropped; query kept; decodes nothing); key both
  a declared URL and the List's with it. The List's pages (`seeAlso`) are the
  `license_urls` table (`records.BUILD_VERSION` 4), indexed by
  `resolveurl.list_url_key` (skips a URL with a fragment). A page naming several
  unrelated licences or only an exception is refused. `URL_ALIASES` and
  `SCANCODE_NOT_SPDX` grow only with a measured package count
  (`working-docs/paper-notes/licence-urls.md`; `docs/lists.md` shows it). Take
  an ID from a path only on a host in `ID_PAGES`. `licenses.nuget.org` paths,
  for that host only, are decoded (`nugetpath`) once, every `%XX` in one pass,
  and must fit `[A-Za-z0-9.+()-]` with words one space apart, which refuses
  `%2F`, `%00`, `%C2%A0`, `%2520` without a list of escapes. Operators upper
  case; a compound is no operand of a compound (`operand names an expression`);
  `url_license_id` brackets one (`(A OR B)`) so a tag keeps precedence.

## Database

- A lookup never creates or writes. `Connections.connect` opens read-only
  (`dbcheck.open_uri`); the detector uses `LicenseDatabase(path,
  create=False)`, whose writes open `mode=rw` and happen only for an older
  schema of licenseid's own file (`dbschema.schema_state`).
  `LicenseDatabase(path)` makes the file at the first write
  (`_ensure_schema`) and refuses a file licenseid did not build, whatever
  `create` is. A missing norm column is filled in memory
  (`dbcache.TableCache.names_and_ids`), never written back.
  No WAL mode: `update` leaves it (`Connections.leave_wal`).
- Every `sqlite3.Error` of a read becomes `DatabaseNotReadyError` in
  `Connections.connection` (`dbcheck.lookup_error`): never wrap per method or
  swallow one. `run 'licenseid update'` only for a file update can rebuild
  (`dbcheck._can_rebuild`).
- One connection per `detect()` call via `LicenseDatabase.reading()`
  (per thread, opened at the first query): query through `_connection()`,
  never `sqlite3.connect`; wrap a new multi-lookup entry point. Only the
  outermost query ends its transaction; each starts with the default
  `row_factory`. Count connections with the `opened` fixture.
- Lookups by ID never scan: `dbcache.TableCache` reads each table's IDs once
  (folded by `listlookup.fold_case`; an unknown ID costs no query), drops
  them when `last_update_datetime` changes (checked once per `reading()`
  block and at every lookup outside one), and keeps no read made during a
  clear (`_generation`). A new write to `licenses` or `license_index` calls
  `self._tables.clear()`, as `_write_db_records` does.
- `text_codes` (optional): the coded texts and a `check` (SHA-256, with
  `textcorpus.CODING_VERSION`). `TextCorpus.restore` gives the corpus `build`
  gives or None, then built in memory, never written back (a BLOB body too);
  a row SQLite cannot decode is `unreadable`. A coding change bumps both.
- Never set `PRAGMA mmap_size`: a file cut by another program (`cp`,
  `truncate`) under a mapped page kills the process with SIGBUS, no message.
- Never build `LIKE` or `GLOB` patterns from input (over 50,000 bytes SQLite
  refuses, read as a broken database); compare in memory.
  `search_candidates` quotes its words.
- A change to the rows `records` builds bumps `records.BUILD_VERSION`; to
  `normalize_text`, `database.NORMALIZATION_VERSION`. Stamps compare as
  numbers; older warns (`build vN outdated`) and `update` rebuilds; newer
  warns `build vN newer`, never rebuilt; a non-number is older. Only a
  database opened without `create` warns.
- `--db` can block or lie: check `stat.S_ISREG`/`S_ISDIR` before opening (a
  FIFO hangs a read-only open; test it in a child with a timeout,
  `db_asserts.probe_check_does_not_hang`). `file::memory:NAME` is a file on
  disk (only `mode=memory` and the exact base `file::memory:` are memory);
  `file://localhost/p` and `?vfs=` are valid. Resolve a path spelling
  once, in `dbcheck._os_file` (`x`, `x/`, `x/.` agree). A symlink loop
  (ELOOP) at the file or above it is `unreadable` for read and write alike,
  before any download (`dbcheck._symlink_loop`); "missing" is
  `dbcheck.is_absent`, never `os.path.exists`/`lexists`, which are False on
  ELOOP.
- `dbcheck`: read is fail-open (`check_database_ready` ignores `unknown`),
  write and delete fail-closed (`reject_foreign_database`). Keep the
  `Refusal` tag on a new condition and decide both policies.
- `Path.unlink(missing_ok=True)` swallows only `FileNotFoundError`: a parent
  that is a file still raises `NotADirectoryError`.
- `database.py` imports `spdx_source` lazily; `spdx_source.py` never
  imports `licenseid.__version__` at module level.
- `detect()` returns the public form (score capped to 1, 4 places). Code or
  a test that ranks or asks "above 1" reads `_match_raw`. `exact` is set
  where a result is made, never derived from the score or the trust: a text
  is exact when the whole non-empty normalised input equals the licence's
  `search_text`; a declared value when a list defines its reading
  (`resolvefirst.is_exact`: `EXACT_CATEGORIES`, not a rewrite rule, not a
  cut value; a tag or field through `ruleread`). White space left off or
  inside a List name (a run, a tab) and a zero-width character
  (`hiddenchars.ZERO_WIDTH`) cut nothing; any other hidden character left
  off does (`hiddenchars.cuts_hidden`). A deprecated name is inexact only when a
  row in use has the same normalised name. The one later change: a variant
  licenseid chose is never exact (`public_result`).
- Packaged bundle: `hatch_build.py` (standard library only) puts it in the
  wheel and sdist (`src/licenseid/data/`, gitignored), steered by
  `LICENSEID_BUNDLE=skip|<path>` and `LICENSEID_REQUIRE_BUNDLE=1` (CI jobs
  that only install the package set `skip`). An
  editable install ships none; only an unpacked sdist (`PKG-INFO`) uses that
  folder. The `offline` fixture hides it; `listindex.packaged_index()` keeps
  one per process (`offline`, `release_fakes.ship` forget it). The hook
  repeats URLs and names of `spdx_source`/`spdxdata`
  (`tests/test_hatch_build.py`). Raise `BUNDLE_VERSION`/`BUNDLE_SHA256`
  with the snapshots in `tests/fixtures/license-list/`
  (`tests/test_releasebuild_pin.py`); `scripts/check_dist_bundle.py`
  checks `dist/`.

## Performance

- `textlocate` bounds the `TEXTS` search by counts, never a clock: past a
  limit, None, never a partial list.
- RapidFuzz costs time in characters, not words. Guard by
  `similarity.build_probe` and `similarity.alignment_affordable`, never by
  characters per word (Japanese and Chinese have no spaces). Before changing
  a limit, sweep real licence texts, Japanese included, at several offsets
  and lengths, on the branch and on `main`, and compare the top answers
  (item 16 in `working-docs/implementation/tech-debt-resolved.md`). Tier 0
  scorers take `score_cutoff=threshold`.
- Tier 1 cost is in trigrams, not words: `ftsquery` cuts a query word to
  `MAX_TERM_CHARS`, above the longest word of any indexed text (70 in List
  3.29.0; `tests/test_ftsquery.py` holds the long-text fixtures to it), before
  `"` is doubled. Time a long word against the real-sized fixture database
  (`tests/long_text_db.py`); a 5-row one cannot fail.
- `\s+` followed by a class that also matches white space (`\s+[\s/*#]*`)
  is quadratic: write `\s[\s/*#]*`. Time every prose regex on
  `"x" + " " * N` (see `test_the_phrase_regex_does_not_backtrack`).
- A fix to input reading can add a quadratic loop (`s = s[1:-1]` per
  bracket, rescanning a line per tag). Time `detect()` end to end (each kept
  candidate costs a Tier 1/2 score) against `main`, with distinct values and
  balanced payloads; report a case over 2x `main`, do not judge it fine. Keep
  deep nesting away from the parser.
- Timing tests: 10x headroom; a bound is `slack(seconds)`
  (`tests/timing.py`, scales for `coverage` and `-n`), never for a ratio of
  sizes. A large input or tight bound is `@pytest.mark.benchmark`
  (`--run-benchmark` before a release) with a small size in the normal run.
  Rerun a timing failure alone before calling it a regression. Details:
  `working-docs/implementation/spdx-expression-reading.md`.

## Python

- Python 3.10 minimum; `requires-python` matches. Idiomatic; built-in types
  unless `collections` is clearly better.
- Full annotations (mypy strict; pyright or pytype for a second opinion);
  minimise `Any`; heavy type-only imports under `if TYPE_CHECKING:`.
  Annotations may be omitted only for: simple literal constants (prefer
  `Final`), enum values, type aliases, `self`/`cls`, `__init__`'s return,
  module dunders. Generic bases take type arguments. Recheck every
  `# noqa:` and `# type: ignore`; reset the mypy cache on odd errors.
- Missing stubs: typeshed, else derive from the source.
- Docstrings use fully qualified names for non-stdlib types
  (`numpy.ndarray`).
- Never: `assert` outside tests, mutable defaults, wildcard imports,
  `pickle`, `eval()` (unless provably safe), hard-coded secrets.
- Check `None`/empty and handle exceptions for all external input.
  `time.monotonic()` for durations. Config in `pyproject.toml`. Zip-safe
  where possible. Packaging metadata follows the Core metadata spec.
- Regexes: mind flags, look-arounds, greediness, multi-line.
- Imports: stdlib, third-party, local; alphabetical in each. Keep an order
  a comment explains (cycles, init).

## Code health

- Boy Scout Rule: leave the code cleaner; refactor during small changes.
  Extract duplicated logic and cohesive pieces early; no dumping-ground modules.
- File size, all files (source, tests, docs): soft ~400-500 lines, hard
  ~800. Split before the soft limit. Backlog:
  `working-docs/design/complexity-and-file-size-roadmap.md`.
- Complexity targets (pylint defaults): Args≤5, Locals≤15, Nesting≤5,
  Branches≤12, Returns≤6, Statements≤50, McCabe≤10, Cognitive≤15. The
  ceilings in `pyproject.toml` and `.flake8` are exact ratchets at the
  current max: never raise one; refactor, and lower it when its last holder
  is gone (re-measure across `src/` and `tests/`).
- Refactor with characterization tests first: pin a bug (`# BUG:`),
  refactor purely, fix in a separate step, flip the pin to a regression
  test.

## Lint and format

Run and fix before committing, with CI's own commands: `ruff check`,
`ruff check --select I` (CI's ruff is newer), `mypy`, `pylint`, `flake8`,
`ruff format`. Ruff, flake8 and pylint cover `src/ tests/ scripts/
benchmarks/ tools/`; pylint runs twice (`src/ tests/`, then the rest: R0801
compares files within one run). Max line length 88.

- Judge `pylint` by its exit code (`pylint src/ tests/ >/dev/null; echo
  $?`): it can print `10.00/10` and exit 16.
- R0801 flags similar inline scripts across test files: put probe scripts
  in `tests/db_asserts.py`.
- Check `ruff --version` before calling an error known.
- Remove unused imports and trailing whitespace.

## File headers

Every source file starts with SPDX tags, keys sorted:

```text
SPDX-FileCopyrightText: <year> <name>
SPDX-FileType: SOURCE                # or DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
```

A `working-docs/` file carries these tags in its YAML front matter, with
`Created` and `Last-Modified` (`YYYY-MM-DD`) in the same block above them.

## Testing

- New behaviour gets tests: success, failure, edge cases. pytest style, no
  `unittest.TestCase`; `spec`/`autospec` mocks; `time_machine` for time;
  `@pytest.mark.parametrize` for similar inputs.
- A new CLI option or API parameter becomes an axis (or a value) in
  `tests/test_option_matrix.py` (a large axis in a file it names, as
  `test_option_matrix_variant.py` and `test_option_matrix_resolve.py`).
- Run plain `pytest tests/` (no `-m 'not benchmark'`), and the full suite
  alone (beside mutants or `tools.golden`, 1 s bounds fail).
- In a fix-and-review loop, run the full suite, the full `tools.golden` and
  `tools.cli_matrix` once, before a push, after the last clean review round,
  not after every fix. Each round runs the linters, the new tests, the tests
  of the changed modules, a mutation check of the new fix, and these always:
  `test_option_matrix` (and `test_option_matrix_resolve` for `resolve()`),
  `test_output_pattern`, `test_resolver_shapes`.
  A change in a shared module (`detector`, `result`,
  `types`, `exprflags`) adds a wider `pytest -n 8` run.
- No `tests/__init__.py`: `from conftest import ...` (helpers
  `make_memory_db_path`, `fake_requests_get`, `leftover_tmp_files`). A
  shared fixture goes in `tests/conftest.py` (importing one trips
  `F811`); plain helpers in a module (`ordering_helpers`, `db_asserts`).
- The autouse `verbose_cli` fixture (`tests/conftest.py`, helpers in
  `tests/cli_verbose.py`) adds `-v` to `detect` and `resolve` under
  `CliRunner` (not a subprocess). A test of the default output or the exact
  command line carries `@pytest.mark.terse_cli`. The CLI golden and
  `tools/cli_matrix` name `--verbose` themselves.
- No network: the autouse `offline` fixture mocks `requests.get`; use
  `conftest.fake_requests_get` and `assert_not_called()` (a second
  `autospec=True` patch over that mock fails on 3.14). Never modify or clear
  the real cache `~/.local/share/licenseid/` (reading it is fine). Database
  tests import the autouse `safe_home` from `tests/db_asserts.py`
  (`# noqa: F401  # pylint: disable=unused-import`).
- `make_memory_db_path` opens its keep-alive connection before building
  `LicenseDatabase` (a shared-cache memory DB dies with its last
  connection): keep that order.
- A negative test on a seeded database passes trivially if its rows have no
  `search_text`. Seed the real near neighbours with text
  (`Lic(..., search_text=...)`, as `tests/test_qualified_plus.py`), mutate
  the fix to see it fail, and probe a full database too.
- Mutation-check new tests: break a line, rerun; clear `__pycache__`
  between mutants; run a mutated copy (`src`, `tests`, `tools`,
  `pyproject.toml`) or a git worktree with `PYTHONPATH` set as in
  "Environment and CI", tests and golden runs included. Mutate with a Python
  script that asserts the old text is there (BSD `sed -i` fails and the
  mutant stays unapplied); "no tests ran" is no kill. A survivor in a helper
  that tests reach only through `resolve()` needs a unit row on the helper.
  Never run a mutation agent while another edits `src/`; diff any snapshot
  first.
- A boundary test writes the number literally (48), not the constant; a
  timing test the old code also passes is inert (assert lookup counts).
  Heuristic code (name rules, readers) gets one independent adversarial
  review of the finished diff: green tests pin the author's reading. A change
  to a signal several readers share (`ranking`, `grantsubject`): grep every
  caller, rerun the full golden.
- Eight tests fail on a clean `main` on the developer's machine (SQLite
  3.51.0): six `wal_copy_without_wal` cases of `test_db_ready.py`, two
  damaged-FTS cases of `test_db_ready_adversarial.py`. Compare with `main`
  before blaming a change.
- Give a huge parameter a short `id` (Windows caps an environment variable,
  and `PYTEST_CURRENT_TEST` holds the ID; `conftest.MAX_TEST_ID` is 300).
  Keep long single words short: Tier 1 cost grows with length.
- A SIGINT test restores the child's handler (`signal.default_int_handler`)
  and signals at a point the child reports (`test_cli_streams._READY`).
- `python -m tools.golden` lists golden answers that moved; a PR that moves
  one lists it with the reason in `tests/harness_changes.py` (a large change
  in a module of its own, `harness_changes_<topic>.py`, merged there).
  Regenerate only when the release is frozen (`tools/golden/README.md`).
- Before a PR touching the CLI, exit codes, streams, input handling or the
  database path, run `python -m tools.cli_matrix --db <copy of a real
  database> --check` (read `tools/cli_matrix/README.md`). A
  `baseline.txt` flag that stops flagging may fail earlier instead: read
  `.cli-matrix/results.json` before deleting it, and record why.
- Accuracy: `test_accuracy.py::test_core_accuracy` every commit;
  `accuracy.yml` on matching-code PRs and weekly. A new module on the
  text-matching path goes into that workflow's `paths`.

## Environment and CI

- Local: the pyenv virtualenv in `.python-version` (`licenseid310`, Python
  3.10, editable); no `.venv`. If it lags `pyproject.toml`, build a scratch
  one: `UV_PROJECT_ENVIRONMENT=<scratch> uv sync --python 3.10
  --all-groups`. Always set `UV_PROJECT_ENVIRONMENT` for `uv run`/`uv sync`
  (else uv makes `.venv`). Stdlib-sensitive changes: also
  `uv run --python 3.14 --group test pytest ...`. Simulate an older Python
  with a module flag, never by deleting stdlib attributes.
- In a git worktree the editable install imports the main checkout: set
  `PYTHONPATH=<worktree>/src:<worktree>/tests:<worktree>` in the same command
  (shell state does not persist; never after a `&&` that can fail), or use a
  scratch `uv` environment (`tools.cli_matrix` needs one). Print
  `licenseid.__file__` when a result looks old.
- Never run the CLI or `tools.cli_matrix` cells with `HOME` unset: Python
  then resolves the real cache.
- CI tests Python 3.10 and 3.14 (Ubuntu) and 3.11 (Windows); builds on
  3.10-3.14 (Ubuntu). CI's 3.10 runs under `coverage`, several times slower.
- Windows on a pull request runs only `pytest -m platform`: the files in
  `tests/platform_files.py`. Every test runs on a push to `main` and on a
  PR labelled `test-all-os` (create it once: `gh label create
  test-all-os`). Linux runs everything.
  - When you add or change a test file, decide on purpose whether it
    belongs in `tests/platform_files.py`: add it if it touches the file
    system, streams, signals, processes, encodings, packaging, or any
    POSIX/Windows difference. `tests/test_platform_files.py` is only a
    heuristic; a missed file fails late, on `main`. Say in the PR which you
    chose.
  - Before touching `dbcheck.py`, a database path or `file:` URI,
    `Path.home()`, or a POSIX-only test (chmod, symlinks, signals,
    `/bin/sh`), read `working-docs/implementation/cross-platform.md`. Mark
    such a test `posix_only`; build a `file://` URI with `Path.as_posix()`.

## Git and pull requests

- **Green CI is not always full CI.** Asked "is it ready to merge?" or "is
  CI green?", count a PR as passing on all platforms only after a full run:
  check the labels (`gh pr view <n> --json labels`) and that the Windows job
  ran the whole suite (`gh pr checks <n>`, the job log), or ask the user. A
  PR without `test-all-os`, or with commits after its full run, has only
  partial CI: say so and ask the user to add the label (never add it or
  merge yourself). A failure on `main` after a merge points to a file
  missing from `tests/platform_files.py`.
- Commit messages: user impact, not implementation
  (<https://chris.beams.io/posts/git-commit/>). Every commit carries
  `Signed-off-by` (DCO check; `git commit -s`).
- Every PR states **What changed?** / **Why?** / **Breaking changes?**
- Asked for a PR title and summary: each in its own fenced block, title
  under 60 characters, summary under 280 as Markdown bullets (code spans
  for flags and keys).
- `CHANGELOG.md` (Keep a Changelog) for significant changes; breaking
  changes marked with short migration steps. An untagged release keeps its
  section open: a PR merged before the tag goes there, not a new
  `[Unreleased]`. Link the PR once it has a number (never guess). Bullets
  ~160 characters, no rationale (link the PR); merge related PRs
  (`[#1], [#2]`); sort by lowest PR number; skip docs, version-bump and
  CI-only noise. In a merge conflict keep every link line, sorted.

## Metadata

- Keep in sync across `pyproject.toml`, `codemeta.json` and other metadata:
  name, version, authors and contributors, licence, description,
  repository URL, keywords (same order).
- `CITATION.cff` is generated from `codemeta.json`
  (`.github/workflows/codemeta2cff.yml`): never edit it. On a release
  update `version`, `dateModified` (becomes `date-released`) and
  `datePublished` in `codemeta.json`.

## Dependencies and security

- Dependencies sorted in `pyproject.toml` (no `requirements.txt` or legacy
  setup files); most current compatible version; verify names
  (typosquatting); remove unused ones; flag abandoned packages with a
  maintained replacement; update regularly to the latest secure versions.
  Verify a version exists and is compatible before suggesting it; prefer
  SemVer.
- No deprecated or insecure libraries or APIs. Validate all input (SQL
  injection, XSS, overflows, path traversal CWE-22). No secrets in code:
  environment or secret manager. Strong, established crypto. OAuth2/OIDC
  for auth.

## Style

- Writing: British English in docs, comments, text; American English in
  code. Active voice, concise, no jargon or idioms, consistent terms,
  acronyms defined on first use, parallel lists, Chicago citations. Short
  comments; do not restate the obvious.
- Markdown: YAML front matter; standard Markdown, no GitHub extensions;
  sentence-case headings; lines ≤80; no bidi control character (GitHub warns;
  write it `\u202e`, `test_docs_status`); run `markdownlint-cli2 "**/*.md"`.
- Names: ASCII letters, digits, `-`, `_`; language conventions; singular
  for one entity, plural for collections and utility modules.
- Shell: mind GNU/BSD/macOS differences; quote variables and paths; mind
  single versus double quotes. zsh (the macOS default) does not word-split
  `$VAR`: use an array or a bash script. `awk length` counts bytes.
- ASCII diagrams: count characters; misalignment is a bug.

## Boundaries

- Ask first: large cross-package refactors, new dependencies with broad
  impact, destructive data or migration changes.
- Never: commit secrets, hand-edit generated files, destructive git
  operations unless asked.
