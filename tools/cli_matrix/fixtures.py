# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The input files every cell can point at, as ``$F/<name>``.

The set is deliberately awkward: line endings the CLI has to normalise,
encodings it has to guess, names a shell has to quote, and entries that are
not readable files at all. They are rebuilt from scratch on every run,
because cells write into their own work directories and a fixture that
drifted between runs would quietly change what a cell tests.
"""

from __future__ import annotations

from pathlib import Path

MIT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    "of this software and associated documentation files (the "
    '"Software"), to deal\n'
    "in the Software without restriction, including without limitation the rights\n"
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
    "copies of the Software, and to permit persons to whom the Software is\n"
    "furnished to do so, subject to the following conditions:\n\n"
    "The above copyright notice and this permission notice shall be included in all\n"
    "copies or substantial portions of the Software.\n\n"
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
    "SOFTWARE.\n"
)

#: A header with non-ASCII letters, so the file is not pure ASCII.
HEAD = "MIT License\n\nCopyright (c) 2020 Jérôme Zoë\n\n"

#: Text that matches no licence, written to ``$F/other.txt``.
OTHER_TEXT = "The quick brown fox jumps over the lazy dog near the river bank\n"

_SYMLINKS = (("link.txt", "mit.txt"), ("broken.txt", "nowhere"))


def make_files(files_dir: Path) -> None:
    """(Re)create every fixture under *files_dir*."""
    files_dir.mkdir(parents=True, exist_ok=True)
    text = HEAD + MIT
    encoded = text.encode()
    written: dict[str, bytes] = {
        # Line endings.
        "mit.txt": encoded,
        "mit_crlf.txt": text.replace("\n", "\r\n").encode(),
        "mit_cr.txt": text.replace("\n", "\r").encode(),
        # Encodings and byte-order marks.
        "mit_bom.txt": b"\xef\xbb\xbf" + encoded,
        "mit_latin1.txt": text.encode("latin-1"),
        "mit_utf16le.txt": text.encode("utf-16-le"),
        "mit_utf16.txt": text.encode("utf-16"),
        # Not text at all, or not usable text.
        "logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        "empty.txt": b"",
        "bom_only.txt": b"\xef\xbb\xbf",
        "ws.txt": b" \r\n\t\n",
        # Names a shell has to quote, or that look like options.
        "with space.txt": encoded,
        "ünï.txt": text.encode("latin-1"),
        "-dash.txt": encoded,
        # No licence in it.
        "other.txt": OTHER_TEXT.encode(),
        # Long text: many unmatched words make a long --diff, which is how
        # a cell provokes SIGPIPE from a short reader.
        "long.txt": (MIT + "extra words here\n" * 3000).encode(),
    }
    for name, data in written.items():
        _write(files_dir / name, data)

    (files_dir / "adir").mkdir(exist_ok=True)
    for name, target in _SYMLINKS:
        link = files_dir / name
        if not link.is_symlink():
            link.unlink(missing_ok=True)
            link.symlink_to(target)

    unreadable = files_dir / "unreadable.txt"
    _write(unreadable, encoded)
    unreadable.chmod(0)


def _write(path: Path, data: bytes) -> None:
    """Write *data*, making the file writable first if a run left it locked."""
    if path.exists() and not path.is_symlink():
        path.chmod(0o600)
    path.write_bytes(data)
