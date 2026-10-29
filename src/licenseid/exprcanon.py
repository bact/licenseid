# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A compound expression: its leaves, its parse, and licenseid's own
canonical order of it (0.7.0 plan, D1).

1. :func:`split` cuts the value into tokens in one pass: brackets of any
   kind, the ``AND`` and ``OR`` operators, and the leaves between them. A
   leaf is ``X``, ``X+``, ``X WITH Y``, with an "or later" grant if it has
   one (decision Q14: an ``or`` that starts a grant, read by
   ``classify.OR_LATER_PHRASE`` through ``looseid.grant_end``, is no
   operator).
2. The caller reads each leaf as a value of its own.
3. :func:`parse` gives the parser a skeleton in which each leaf is a
   placeholder ``LicenseRef-licenseid-leaf-N``: ``py-spdx-license`` then
   sees only ``AND``, ``OR``, brackets and references, so neither its
   snapshot of the List, nor its want of ``+`` and ``AdditionRef-``, nor its
   sort (findings F1 to F3) can change the answer.
4. :func:`canonical` flattens chains of one operator, sorts, removes
   repeats and renders with the brackets precedence needs, and names each
   change as a step: ``operator_case``, ``whitespace``, ``brackets``,
   ``reorder``, ``dedupe``.

The order (decisions Q19, Q24): every leaf before every bracketed group; a
leaf by its rank (a listed ID 0, a ``LicenseRef-``/``DocumentRef-`` 1, a
``WITH`` 2), then its text case-folded, then as is; a group by its rendered
text, the same way. Commutativity, idempotence and associativity of AND and
OR keep the meaning (SPDX 3, Annex D: AND binds tighter than OR).
"""

import re
from collections.abc import Iterable
from typing import Final, NamedTuple

import py_spdx_license

from licenseid.exprtokens import OPERATOR
from licenseid.identifiers import MAX_PARSE_DEPTH, MAX_PARSE_OPERATORS, parse_expression
from licenseid.looseid import RE_GRANT_WORDS, grant_end
from licenseid.resolvertypes import Step, step

# A bracket of any kind, or an operator word (WITH stays in its leaf).
_RE_PART: Final = re.compile(rf"[()\[\]{{}}]|{OPERATOR}", re.IGNORECASE)
_OPENS: Final = {"(": ")", "[": "]", "{": "}"}
_CLOSES: Final = frozenset(_OPENS.values())
_PLACEHOLDER: Final = "LicenseRef-licenseid-leaf-"
_LEAF: Final = "leaf"


class Token(NamedTuple):
    """A part of the value: ``leaf``, ``AND``, ``OR`` or a bracket
    character, and its ``[start, end)`` in the text given to :func:`split`."""

    kind: str
    start: int
    end: int


class Group(NamedTuple):
    """An operator and its operands, a leaf being its index in the value."""

    operator: str
    children: tuple["Node", ...]


Node = int | Group


def unbracketed(text: str) -> str:
    """*text* without the brackets around the whole of it, of any kind
    (``(MIT)``, ``[MIT]``, ``{[MIT]}``; decision Q21), as
    ``identifiers.without_outer_brackets`` takes round ones: one pass, the
    shallowest depth between the leading and trailing runs is how many pairs
    go (``[A] OR [B]``: none). A pair of two kinds (``[MIT)``) stays, for the
    compound reader to refuse."""
    lead = len(text) - len(text.lstrip("([{"))
    trail = len(text) - len(text.rstrip(")]}"))
    depth = shallowest = lead
    for char in text[lead : len(text) - trail]:
        if char in _OPENS:
            depth += 1
        elif char in _CLOSES:
            depth -= 1
            shallowest = min(shallowest, depth)
    pairs = 0
    while pairs < min(shallowest, trail) and _OPENS[text[pairs]] == text[-1 - pairs]:
        pairs += 1
    return text[pairs : len(text) - pairs]


def split(text: str) -> list[Token]:
    """The tokens of *text*, a value trimmed at both ends. An operator stands
    between white space or brackets; anything else is part of a leaf. One
    pass: each "or" is asked once whether a grant starts there."""
    tokens: list[Token] = []
    lead = skip = 0  # where the current leaf starts; where a grant ended
    for part in _RE_PART.finditer(text):
        if part.start() < skip:
            continue
        word = part.group(0).upper()
        if word == "WITH" or (word in ("AND", "OR") and not _delimited(text, part)):
            continue
        grant = _grant(text, part) if word in ("OR", "(", "[") else None
        if grant is not None and text[lead : part.start()].strip():
            skip = grant  # an "or" right after an operator or a bracket is one
            continue
        _add_leaf(text, lead, part.start(), tokens)
        tokens.append(Token(word, part.start(), part.end()))
        lead = part.end()
    _add_leaf(text, lead, len(text), tokens)
    return tokens


def _delimited(text: str, part: re.Match[str]) -> bool:
    """Whether the operator word *part* has white space, a bracket or an end
    of *text* on both sides (``MIT"OR"ISC`` holds no operator)."""
    before = text[part.start() - 1] if part.start() else " "
    after = text[part.end()] if part.end() < len(text) else " "
    return all(char.isspace() or char in "()[]{}" for char in (before, after))


def _grant(text: str, part: re.Match[str]) -> int | None:
    """Where the grant that starts at *part* ends, if it is one: an ``or``,
    or a bracket and an ``or`` (``(or later)``), the phrase, its words
    ("version", "of the License"), the closing bracket; then white space, a
    closing bracket or the end."""
    start, close = part.start(), ""
    if part.group(0) in "([":
        close = _OPENS[part.group(0)]
        start = _after_space(text, part.end())
    if text[start : start + 2].lower() != "or":
        return None
    end = grant_end(text, start)
    if end is None:
        return None
    words = RE_GRANT_WORDS.match(text, end)
    end = words.end() if words else end
    if close:
        end = _after_space(text, end)
        if text[end : end + 1] != close:
            return None
        end += 1
    after = text[end : end + 1]
    return end if not after or after.isspace() or after in _CLOSES else None


def _after_space(text: str, pos: int) -> int:
    """The first position from *pos* on that is not white space."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _add_leaf(text: str, start: int, end: int, tokens: list[Token]) -> None:
    """Add ``text[start:end]``, trimmed, as a leaf, if anything is left."""
    segment = text[start:end]
    if segment.strip():
        lead = len(segment) - len(segment.lstrip())
        trail = len(segment) - len(segment.rstrip())
        tokens.append(Token(_LEAF, start + lead, end - trail))


def leaves(tokens: list[Token]) -> list[Token]:
    """The leaf tokens, in input order."""
    return [token for token in tokens if token.kind == _LEAF]


def oversize(tokens: list[Token]) -> str | None:
    """Why the parser is not given *tokens* (``too many operators``, ``too
    deeply nested``, as ``identifiers.parse_expression`` would refuse them),
    ``mismatched brackets`` for a pair of two kinds (``[MIT)``), or None."""
    operators = sum(token.kind in ("AND", "OR") for token in tokens)
    if operators > MAX_PARSE_OPERATORS:
        return "too many operators"
    opened: list[str] = []
    for token in tokens:
        if token.kind in _OPENS:
            opened.append(_OPENS[token.kind])
            if len(opened) > MAX_PARSE_DEPTH:
                return "too deeply nested"
        elif token.kind in _CLOSES and opened and opened.pop() != token.kind:
            return "mismatched brackets"
    return None


def written_upper(text: str, tokens: list[Token]) -> bool:
    """Whether every ``AND`` and ``OR`` of *tokens* is written in upper case
    in *text*, as SPDX spells them; a lower-case "or" may be prose."""
    return all(
        text[token.start : token.end].isupper()
        for token in tokens
        if token.kind in ("AND", "OR")
    )


def missing_operator(tokens: list[Token]) -> bool:
    """Whether two operands stand in *tokens* with no operator between them
    (a leaf or a closing bracket, then a leaf or an opening bracket): prose
    with a bracket, not an expression the grammar refuses."""
    ended = False  # the token before ends an operand
    for token in tokens:
        if ended and (token.kind == _LEAF or token.kind in _OPENS):
            return True
        ended = token.kind == _LEAF or token.kind in _CLOSES
    return False


def parse(tokens: list[Token], texts: list[str]) -> Node | str:
    """The tree of *tokens*, parsed by ``py-spdx-license`` with a placeholder
    for each leaf; ``parse failed: <message>`` if the parser refuses it (its
    message, each placeholder shown as the leaf's text, *texts*)."""
    skeleton = " ".join(_skeleton(tokens))
    tree = parse_expression(skeleton)
    if tree is not None:
        return _node(tree)
    message = "not an expression"
    try:  # again, for the message: the skeleton is small (oversize)
        py_spdx_license.parse(skeleton, allow_unknown=True)
    except Exception as error:  # pylint: disable=broad-exception-caught
        message = str(error)
    for index, text in enumerate(texts):
        message = message.replace(f"{_PLACEHOLDER}{index}", text)
    return f"parse failed: {message}"


def _skeleton(tokens: list[Token]) -> list[str]:
    """The words of the skeleton: ``(``, ``)``, an operator, or the
    placeholder of a leaf, numbered by its place among the leaves."""
    words, index = [], 0
    for token in tokens:
        if token.kind == _LEAF:
            words.append(f"{_PLACEHOLDER}{index}")
            index += 1
        elif token.kind in _OPENS:
            words.append("(")
        else:
            words.append(")" if token.kind in _CLOSES else token.kind)
    return words


def _node(tree: py_spdx_license.Node) -> Node:
    """Our tree of a parsed skeleton: a leaf index, or an operator and its
    operands (brackets are no node: the tree holds the grouping)."""
    while isinstance(tree, py_spdx_license.CompoundExpression):
        tree = tree.child
    if isinstance(tree, py_spdx_license.LicenseRef):
        return int(tree.ident[len(_PLACEHOLDER) :])
    return Group(tree.NAME, tuple(_node(child) for child in tree.children))


def leaf_key(expression: str) -> tuple[int, str, str]:
    """The sort key of a resolved leaf: ``(rank, case-folded, as is)``."""
    if " WITH " in expression:
        rank = 2
    elif expression.lower().startswith(("licenseref-", "documentref-")):
        rank = 1
    else:
        rank = 0
    return rank, expression.casefold(), expression


def canonical(
    text: str, tokens: list[Token], tree: Node, texts: list[str]
) -> tuple[str, list[Step]]:
    """The canonical expression of *text*, whose leaves resolved to
    *texts*, and the steps that lead to it from the leaves as resolved."""
    keys = [leaf_key(expression) for expression in texts]
    forms = [_written(text, tokens, texts, upper=False)]
    forms.append(_written(text, tokens, texts, upper=True))
    forms.append(_spaced(text, tokens, texts))
    flat = _flat(tree)
    forms.append(_render(flat, texts))
    forms.append(_render(_ordered(flat, texts, keys, dedupe=False), texts))
    forms.append(_render(_ordered(flat, texts, keys, dedupe=True), texts))
    kinds = ("operator_case", "whitespace", "brackets", "reorder", "dedupe")
    steps = [
        step(kind, True, before, after)
        for kind, before, after in zip(kinds, forms, forms[1:])
        if before != after
    ]
    return forms[-1], steps


def _written(text: str, tokens: list[Token], texts: list[str], upper: bool) -> str:
    """*text* with each leaf replaced by its resolved text, the operators in
    upper case if *upper*, the spacing and brackets as written."""
    out, end, index = [], 0, 0
    for token in tokens:
        out.append(text[end : token.start])
        if token.kind == _LEAF:
            out.append(texts[index])
            index += 1
        else:
            word = text[token.start : token.end]
            out.append(word.upper() if upper else word)
        end = token.end
    return "".join(out)


def _spaced(text: str, tokens: list[Token], texts: list[str]) -> str:
    """The tokens one space apart, none inside a bracket: the spacing of a
    rendered expression, the brackets still as written."""
    words = iter(texts)
    out = ""
    for token in tokens:
        word = next(words) if token.kind == _LEAF else text[token.start : token.end]
        if out and not out.endswith(tuple(_OPENS)) and token.kind not in _CLOSES:
            out += " "
        out += word.upper() if token.kind in ("AND", "OR") else word
    return out


def _flat(node: Node) -> Node:
    """*node* with each chain of one operator made one group: ``A OR (B OR
    C)`` is ``A OR B OR C`` (associativity)."""
    if isinstance(node, int):
        return node
    return Group(node.operator, _spliced(node.operator, map(_flat, node.children)))


def _spliced(operator: str, children: Iterable[Node]) -> tuple[Node, ...]:
    """*children*, a child of the same *operator* replaced by its own."""
    out: list[Node] = []
    for child in children:
        if isinstance(child, Group) and child.operator == operator:
            out.extend(child.children)
        else:
            out.append(child)
    return tuple(out)


def _render(node: Node, texts: list[str]) -> str:
    """*node* as an expression: brackets only where precedence needs them,
    around an OR inside an AND."""
    if isinstance(node, int):
        return texts[node]
    parts = []
    for child in node.children:
        rendered = _render(child, texts)
        if isinstance(child, Group) and (child.operator, node.operator) == (
            "OR",
            "AND",
        ):
            rendered = f"({rendered})"
        parts.append(rendered)
    return f" {node.operator} ".join(parts)


def _text_key(text: str) -> tuple[str, str]:
    """Case-folded, then as is: the SPDX License List's order, made total
    (decision Q24)."""
    return text.casefold(), text


def _ordered(
    node: Node, texts: list[str], keys: list[tuple[int, str, str]], dedupe: bool
) -> Node:
    """*node* in canonical order: leaves by key, then groups by rendered
    text; with *dedupe*, each operand once, and a group of one operand is
    that operand (idempotence)."""
    if isinstance(node, int):
        return node
    children = [_ordered(child, texts, keys, dedupe) for child in node.children]
    flat = _spliced(node.operator, children)  # a repeat removed below can
    # leave a group of the parent's operator: (A OR A) AND B is A AND B
    ints = sorted((c for c in flat if isinstance(c, int)), key=lambda c: keys[c])
    groups = sorted(
        (c for c in flat if isinstance(c, Group)),
        key=lambda c: _text_key(_render(c, texts)),
    )
    ordered: list[Node] = [*ints, *groups]
    if dedupe:
        seen: dict[str, Node] = {}
        for child in ordered:
            seen.setdefault(_render(child, texts), child)
        ordered = list(seen.values())
    return ordered[0] if len(ordered) == 1 else Group(node.operator, tuple(ordered))
