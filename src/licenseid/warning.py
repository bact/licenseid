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
import re
import threading
import warnings
from collections.abc import Iterator
from types import FrameType


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

# A frame of licenseid's own code, by the name of its module: a file name
# would not match in a frozen or sourceless install, where co_filename is
# the path the bytecode was compiled at.
_PACKAGE = "licenseid"


@contextlib.contextmanager
def once() -> Iterator[None]:
    """Within the block, a warning this process gave in such a block before
    (the same text) is not given again: what ``resolve()`` and ``detect()``
    say about a database they open (the one at the default path, or a path
    given as ``db``), which they open again when its file changes, and
    ``resolve()``'s fallback to the packaged list. A warning the caller's
    filter turned into an error, or ignored, was not given: it is given at
    the next call, as Python's own registry marks only a warning shown."""
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
    code that called into licenseid. Python's default filter shows a
    warning once per text and place (file and line): a warning with another
    detail, from the same line, is shown again."""
    warning = LicenseIdWarning(subject, condition, detail, action)
    text = str(warning)
    level, caller = _caller()
    if _ONCE.get():
        with _LOCK:
            if text in _given:
                return
    warnings.warn(warning, stacklevel=level)  # raises under an "error" filter
    if _ONCE.get() and not _ignored(warning, caller):
        with _LOCK:
            _given.add(text)


def _ignored(warning: LicenseIdWarning, caller: FrameType | None) -> bool:
    """Whether the filters in force ignore *warning* given at *caller*: the
    first filter that matches decides, as ``warnings.warn_explicit`` reads
    the list (category a subclass; message from the start, case folded;
    module name from the start; line 0 for any), else the default
    action. The category is tested first, and a field only when the ones
    before it matched, as CPython does."""
    module = "sys" if caller is None else caller.f_globals.get("__name__", "")
    lineno = 0 if caller is None else caller.f_lineno
    text = str(warning)
    for action, message, category, name, line in warnings.filters:
        if (
            issubclass(LicenseIdWarning, category)
            and _matches(message, text)
            and _matches(name, module)
            and line in (0, lineno)
        ):
            return action == "ignore"
    # Not in typeshed; "default" in CPython, where nothing changed it.
    return getattr(warnings, "defaultaction", "default") == "ignore"


def _matches(pattern: re.Pattern[str] | str | None, value: str) -> bool:
    """Whether a filter's message or module field *pattern* matches *value*,
    as CPython's ``check_matched`` reads it: None matches any value, a plain
    ``str`` only an equal one (the module of the built-in default filter,
    ``('default', None, DeprecationWarning, '__main__', 0)``), and a
    compiled pattern (``filterwarnings``, ``-W``) from the start."""
    if pattern is None:
        return True
    if isinstance(pattern, str):
        return pattern == value
    return pattern.match(value) is not None


def _ours(frame: FrameType) -> bool:
    name = frame.f_globals.get("__name__", "")
    return isinstance(name, str) and (
        name == _PACKAGE or name.startswith(f"{_PACKAGE}.")
    )


def _caller() -> tuple[int, FrameType | None]:
    """The ``stacklevel`` of the frame that called the outermost licenseid
    frame (the caller's code, not licenseid's), and that frame.
    ``warnings.warn`` counts the frame that calls it (:func:`warn`) as 1. A
    frame between two of licenseid's (``functools.cached_property``) does
    not end the walk."""
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:  # an interpreter without frames
        return 2, None
    frames: list[FrameType] = []
    frame = frame.f_back.f_back  # warn()'s caller: level 2
    while frame is not None:
        frames.append(frame)
        frame = frame.f_back
    outermost = max((i for i, f in enumerate(frames) if _ours(f)), default=-1)
    index = outermost + 1  # the frame after the outermost of ours
    return index + 2, frames[index] if index < len(frames) else None
