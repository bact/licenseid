# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The warnings licenseid gives, through Python's :mod:`warnings`.

A library warns and lets its caller decide: record, silence, raise or show.
Every warning licenseid gives is a :class:`LicenseIdWarning` given by
:func:`warn`, the one emitter; no library code writes a warning to standard
error itself. The CLI prints each one as its ``WARNING: ...`` line
(``licenseid.clicommon.printed_warnings``).

Standard library only, so any module can import it.
"""

import contextlib
import contextvars
import inspect
import os
import threading
import warnings
from collections.abc import Iterator


class LicenseIdWarning(UserWarning):
    """A warning of licenseid: a fallback taken or a guess made, after which
    the call goes on.

    Its text is ``SUBJECT: CONDITION[: DETAIL][; ACTION]``, the grammar of
    every licenseid diagnostic, and the CLI prints it after ``WARNING: ``.
    The parts are attributes: ``subject`` (``database``, ``input``, a cache
    file's name), ``condition`` (``build v2 outdated``,
    ``variant not stated``), ``detail`` and ``action`` (None when not
    stated).
    """

    subject: str
    condition: str
    detail: str | None
    action: str | None

    def __init__(
        self,
        subject: str,
        condition: str,
        detail: str | None = None,
        action: str | None = None,
    ) -> None:
        text = f"{subject}: {condition}"
        if detail is not None:
            text += f": {detail}"
        if action is not None:
            text += f"; {action}"
        super().__init__(text)
        self.subject = subject
        self.condition = condition
        self.detail = detail
        self.action = action

    def __reduce__(
        self,
    ) -> tuple[type["LicenseIdWarning"], tuple[str, str, str | None, str | None]]:
        # BaseException would rebuild it from its text alone.
        return type(self), (self.subject, self.condition, self.detail, self.action)


def parts(text: str) -> tuple[str, str, str | None]:
    """*text*, worded ``SUBJECT: CONDITION[: DETAIL]`` (the message of a
    ``licenseid.errors.LicenseIdError`` a fallback follows), as its subject,
    condition and detail (None when there is none). A subject is a word or
    a file name and a condition a short phrase, neither with ``": "`` in it,
    so the detail is all that follows the second one."""
    subject, _, rest = text.partition(": ")
    condition, separator, detail = rest.partition(": ")
    return subject, condition, detail if separator else None


# Within once(): the texts given in this process, each given only once.
_ONCE: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "licenseid_warn_once", default=False
)
_LOCK = threading.Lock()
_given: set[str] = set()

_PACKAGE = os.path.normcase(os.path.dirname(os.path.abspath(__file__))) + os.sep


@contextlib.contextmanager
def once() -> Iterator[None]:
    """Within the block, a warning this process gave in such a block before
    (the same text) is not given again: what ``match()`` and ``detect()``
    say about the database at the default path, which they open again when
    its file changes."""
    token = _ONCE.set(True)
    try:
        yield
    finally:
        _ONCE.reset(token)


def reset_once() -> None:
    """Forget the warnings :func:`once` gave, for a test that expects one."""
    with _LOCK:
        _given.clear()


def warn(
    subject: str,
    condition: str,
    detail: str | None = None,
    action: str | None = None,
) -> None:
    """Give the :class:`LicenseIdWarning` of these parts, attributed to the
    code that called into licenseid (its file and line, which Python's
    default filter shows once per place)."""
    warning = LicenseIdWarning(subject, condition, detail, action)
    if _ONCE.get():
        with _LOCK:
            if str(warning) in _given:
                return
            _given.add(str(warning))
    warnings.warn(warning, stacklevel=_caller_level())


def _caller_level() -> int:
    """The ``stacklevel`` of the frame that called the outermost licenseid
    frame: the caller's code, not licenseid's. ``warnings.warn`` counts the
    frame that calls it (:func:`warn`) as 1."""
    frame = inspect.currentframe()
    if frame is None:  # an interpreter without frames
        return 2
    level, outermost = 1, 1
    frame = frame.f_back  # warn()
    while frame is not None:
        if os.path.normcase(frame.f_code.co_filename).startswith(_PACKAGE):
            outermost = level
        frame = frame.f_back
        level += 1
    return outermost + 1
