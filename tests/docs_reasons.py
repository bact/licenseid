# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A value for each refusal condition of docs/resolve.md that the resolver
fixtures do not reach (roadmap item 57). ``test_docs_vocabulary`` resolves
them with the corpus and holds every listed condition to the result."""

from licenseid.identifiers import MAX_PARSE_DEPTH, MAX_PARSE_OPERATORS
from licenseid.resolver import MAX_EXPRESSION_CHARS

#: ``condition: value``; the condition is the reason up to its first colon.
REASON_EXAMPLES = {
    "empty": '""',
    "mismatched brackets": "(MIT]",
    "plus after a bracket": "(MIT)+",
    "plus after an exception": "MIT WITH Classpath-exception-2.0+",
    "qualifier on a reference": "LicenseRef-x+",
    "too deeply nested": (
        "MIT OR " + "(" * (MAX_PARSE_DEPTH + 1) + "ISC" + ")" * (MAX_PARSE_DEPTH + 1)
    ),
    "too long": "x" * (MAX_EXPRESSION_CHARS + 1),
    "too many operators": "MIT" + " OR MIT" * (MAX_PARSE_OPERATORS + 1),
    "url names a licence with an exception": (
        "https://github.com/maranget/hevea/blob/master/LICENSE"
    ),
    "url names an exception": (
        "http://directory.fedoraproject.org/wiki/GPL_Exception_License_Text"
    ),
    "word dropped": "REM MIT",
}
