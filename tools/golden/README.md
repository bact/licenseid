# Golden snapshots

The pre-release harness records what `detect()` and every CLI command answer
on a fixed set of inputs, and fails when an answer moves that no pull request
listed. The files are in `tests/fixtures/golden/` (see the section
"10. `golden`" of `tests/fixtures/README.md`).

## Commands

```shell
# What differs from the files (exit 1 if anything does):
python -m tools.golden
# Rewrite the files from the tree you are on:
python -m tools.golden --write
# One part only: id, name, short, long, mixed, cli
python -m tools.golden --write cli
```

`long` and `short` run `detect()` on 185 and 695 texts and take about ten
minutes together; the other parts take seconds. The run needs the test
dependencies and no network.

## What a pull request does

1. Run `python -m tools.golden` on the branch. It prints each case that moved,
   the old and the new value.
2. List each one in `tests/harness_changes.py` with the new value and the
   reason (`DETECT_CHANGES`, or `CLI_CHANGES` by the digest the command
   prints). The tests accept those changes and no other, and fail when a
   listed case did not move.
3. After the release is frozen, run `--write` and empty both tables.

Never edit a golden file by hand.

## Files

| File | Rows | One row is |
| --- | --- | --- |
| `detect_id.tsv`, `detect_name.tsv` | one per spelling | the top result for an ID or a name, as the fixture spells it |
| `detect_short.tsv` | one per licence | a head or tail slice of its text (300 to 2,000 characters) |
| `detect_long.tsv` | every third licence | its verbatim text |
| `detect_mixed.tsv` | one per file | a file of `mixed-content` or `mixed-content-curated` |
| `cli.jsonl` | one per case and mode | exit status, standard output and standard error of a command, as text and with `--json` |

The detect rows hold the expression, the method, `exact` and the score to four
places. The `detect()` database is the one of the long-text fixtures
(`tests/harness_db.py`). The CLI cases are in `tests/harness_cli.py`; they run
on a database and a shipped list built from the fixtures, a network that is
down and a scratch home, and name the scratch paths `<DB>` and `<TMP>`.

Every commit runs a slice (`SLICE_STRIDE` in `tests/harness_golden.py`) and
every CLI case; `pytest --run-benchmark` runs every case.
