# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The channels a declared value reaches (the grant tests): ``resolve()``, the
argument, an SPDX tag and a JSON ``license`` field, on the full List
(``corpus_db``)."""

import json
import warnings
from collections.abc import Callable
from typing import Final

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector

#: Each channel as the text ``detect()`` reads.
CHANNELS: Final[dict[str, Callable[[str], str]]] = {
    "argument": lambda value: value,
    "tag": lambda value: f"SPDX-License-Identifier: {value}\n",
    "field": lambda value: json.dumps({"license": value}),
}

#: ``(expression, exact)`` of the first result, or None for no answer.
Answer = tuple[str, bool] | None


def answers(db: LicenseDatabase, value: str) -> dict[str, Answer]:
    """The first answer of each channel for *value*; a channel with none is
    None."""
    detector = LicenseDetector(db.location)
    found: dict[str, Answer] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, text in CHANNELS.items():
            top = detector.detect(text=text(value))[:1]
            found[name] = (top[0]["expression"], top[0]["exact"]) if top else None
    return found


def refused(db: LicenseDatabase, value: str) -> str | None:
    """The reason ``resolve()`` refuses *value* for, or None if it reads it."""
    return resolve(value, db)["reason"]
