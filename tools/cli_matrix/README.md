# CLI matrix

A harness that runs the `licenseid` command line as a real process, in a
real shell, under a real operating system, and judges what comes back.

## Why it exists

The pytest suite calls the CLI in-process, through click's test runner,
with monkeypatched I/O. That is fast and precise, and it is blind to
everything between the code and the user: the shell that quotes the
arguments, the locale whose codec cannot encode the answer, the file
descriptor someone closed, the signal that arrives mid-match, the `HOME`
that turns out to be a file, the input that is larger than `ARG_MAX`.

Every FLAG this tool has produced so far was a defect the test suite could
not reach. It is not a replacement for pytest; it is the other half.

## When to run it

- Before a pull request that touches argument parsing, input handling,
  output formatting, diagnostics, the database path, or `update`.
- After changing anything about how the process starts or exits.
- When a bug report mentions a shell, a locale, a pipe or a terminal.

It is not part of continuous integration: it needs a real licence database
and several minutes.

## Prerequisites

- macOS or Linux. Windows is not supported and the tool refuses to run
  there: there are no POSIX shells, signals or file modes to exercise.
- A real licence database, built by `licenseid update`. Copy it out of the
  cache first; the tool refuses a path inside `~/.local/share/licenseid`.
- One or more Python environments with `licenseid` installed, each with a
  `licenseid` script next to the interpreter.
- Optionally `bash`, `zsh`, `sh`, `dash` and `ksh`. Whichever are missing
  are reported in the ledger and their cells are skipped.

## Usage

```shell
cp ~/.local/share/licenseid/licenses.db /tmp/matrix.db

python -m tools.cli_matrix --db /tmp/matrix.db
python -m tools.cli_matrix --db /tmp/matrix.db E2 E4     # only two families
python -m tools.cli_matrix --db /tmp/matrix.db --check   # against the baseline
```

Two interpreters, which is what makes the cross-version comparison
meaningful:

```shell
python -m tools.cli_matrix --db /tmp/matrix.db \
    --python 310=/path/to/py310/bin/python \
    --python 314=/path/to/py314/bin/python
```

A full run of about 1200 cells across five shells and two interpreters
takes roughly three minutes on a laptop, most of it process start-up.

## Options

| option | meaning |
| --- | --- |
| `family ...` | only run cells whose family starts with this prefix |
| `--db PATH` | the database to test against; required, or by env var |
| `--python LABEL=PATH` | an interpreter to test, repeatable |
| `--shell NAME` | a shell to test, repeatable |
| `--out DIR` | output directory, default `<repo>/.cli-matrix/` |
| `--jobs N` | cells to run at once, default 6 |
| `--list` | print cell ids and descriptions, run nothing |
| `--compare` | report flags that are new or fixed against the baseline |
| `--check` | as `--compare`, but exit 1 when anything is new |
| `--update-baseline` | rewrite `baseline.txt` from a full run |

The default interpreter is `current=<sys.executable>`. The default shells
are those of `bash zsh sh dash ksh` found on `PATH`.

## Verdicts

`PASS`
: Every invariant holds, and so does whatever this cell was documented to
  do. Only a cell with a documented expectation can pass.

`OBSERVE`
: Nothing was violated, but nothing was promised either. The behaviour is
  recorded in the ledger for a human to judge. Most cells land here on
  purpose: the point is to see what the CLI does, not to freeze it.

`FLAG`
: An invariant or a documented expectation is violated. The invariants come
  from `AGENTS.md` under "CLI output": stdout carries only results, every
  diagnostic goes to stderr in the `LEVEL: SUBJECT: CONDITION` grammar, a
  predicate answers `true`, `false` or a usage error, `match` prints one of
  its three documented shapes, exit statuses are 0, 1 or 2, and nothing ever
  shows a traceback. A cell also flags when its answer depends on the shell
  or the interpreter, when the five predicates contradict each other, or
  when `update` leaves temporary files behind.

A cell that could not run is a `SKIP`, listed in the ledger with its
reason. A skip is never a pass.

## Output

Everything lands in `--out`:

`ledger.md`
: Every FLAG and every OBSERVE spelled out, with the exit status, the start
  of stdout, the first line of stderr and the notes that explain the
  verdict; then what was skipped; then a table of every execution. Paths
  are normalised to `$W` (the cell's work directory) and `$O` (the output
  directory), so two ledgers from two machines can be diffed.

`coverage.md`
: Not "did it pass" but "did anything try this". A row per subcommand and
  flag with the number of cells, shells and interpreters behind it, the
  input sources each command was fed from, which pairs of `match` flags
  were ever used together, and which pairs were not.

`results.json`
: One object per execution, including the full stdout and stderr. The
  baseline and any later diff are computed from this.

`work/`, `home/`, `files/`, `bin/`, `db/`
: The sandbox: one work directory per execution, the fixture inputs, the
  generated offline launcher wrappers, and the copy of the database.

## The baseline

Around ninety cells flag on a healthy tree. They are real, open findings,
and reprinting them on every run would bury the one new flag that a change
just introduced. `baseline.txt` records the known set, one
`<cell-id> <shell>` per line, sorted, so a version-control diff of it reads
as "this was fixed" or "this appeared". The interpreter label is not part
of the key (a cell that flags on any interpreter is a known flag), so the
baseline works with whatever `--python` labels you choose.

```shell
python -m tools.cli_matrix --db /tmp/matrix.db --check
```

prints `NEW_FLAG` lines for anything not in the baseline, `FIXED_FLAG`
lines for baseline entries that no longer flag, and exits 1 if there is
anything new. Only cells that actually ran can be called fixed, so a
filtered run never claims the rest of the matrix is clean.

After fixing a defect, remove its line by hand, or regenerate:

```shell
python -m tools.cli_matrix --db /tmp/matrix.db --update-baseline
```

which is refused with a family or `--shell` filter, since it would erase
every cell the filter left out. Run it with the interpreters you normally
use, so a flag that only one of them shows is recorded.

## Adding a cell

Cells live in `cells/`: `match.py` (A), `predicate.py` (B),
`global_options.py` (C), `update.py` (D), `environment.py` (E1 to E6, the
streams around the process) and `process_env.py` (E7 to E11, its own
resources), with the shared command list in `core_commands.py`. Add yours
to the family it belongs to, at the end, so the identifiers of the existing
cells do not shift. A cell is declarative:

```python
cells.add(
    "E11",
    "env: PYTHONWARNINGS=error",
    "PYTHONWARNINGS=error " + licenseid("match --bold $F/mit.txt"),
    kind="match",
    exp_exit=0,
)
```

The command is a shell string on purpose: building an argument list would
hide exactly the quoting and word-splitting differences the tool looks for.
It may use `$L` (the `licenseid` script under test), `$LU` (its offline
launcher), `$DB` (the database copy), `$F` (the fixtures), `$W` (this
cell's own work directory) and `$HOME` (a home inside `$W`).

Give `exp_exit`, `exp_out` or `exp_err` only where the behaviour really is
documented. Without them the cell is an `OBSERVE`, which is the honest
verdict for anything unspecified. Set `xenv=False` when an answer is
genuinely allowed to differ between shells, `merged=True` when the command
itself mixes the two streams, `progress=True` when free text on stderr is
expected, and `tty=True` to run under a pseudo-terminal.

If a new input file is needed, add it to `fixtures.py`, where the whole set
is rebuilt from scratch on every run.

## Safety

- The database under test is copied into `--out`; no cell is ever pointed
  at the original, and a path inside the real cache is refused outright.
- `HOME` for every cell is inside that cell's own work directory, so cells
  that write under `HOME` cannot race each other or reach the real one.
- The real cache, `~/.local/share/licenseid`, is never opened, and the run
  proves it: the tool records every entry's size and modification time
  before and after, and exits 2 if anything changed, whatever the verdicts.
  Four cells that would resolve the default database path to it (`HOME` unset, where
  Python falls back to the password database) are permanently skipped with
  that reason. An earlier version of this harness ran them, and one of them
  deleted the developer's own `licenses.db`.
- `update` runs only through `launcher.py`, whose `requests.get` is a
  scripted fake. A start-up self-check scripts the network down and refuses
  to run unless the fake's own wording comes back, so the day the
  replacement stops working the matrix stops too.
- Proxy variables point at a dead local port, so a request that somehow
  escaped the fake fails instead of reaching the network. One family, `D4`,
  uses the real request stack deliberately, to check that a blocked network
  fails the documented way.

## Known limits

- Cells whose command ends in a pipe or an `echo` (E4, E5, some E6) report the
  exit status of the last command, not the CLI's, so the exit-code and
  output-shape checks are skipped for them. They still catch tracebacks,
  diagnostics on stdout and lines outside the grammar.
- E9 (concurrency) depends on timing: a cell may finish before the race it
  looks for begins. A clean E9 is not proof.
- The tool refuses to run as root, because several cells create
  directories under odd `HOME` values such as `/nonexistent`.
- A signal test needs SIGINT reset first: a non-interactive shell starts a
  background job with SIGINT ignored, and Python then never handles it. The
  cells do this through `RESET_SIGINT`; copy it for a new signal cell.

## Platform notes

Written for macOS and Linux both. `script(1)` is replaced by Python's
`pty`, `md5` by `cksum`, and cells that name a specific locale run only
when `locale -a` lists it. `ulimit -v` exists on Linux and not on macOS;
that cell is an observation on both, so a starved process cannot flag.
