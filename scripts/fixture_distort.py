# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Text distortions used by the licenseid fixture generator."""

import random
import re
import string


def generate_foreign_texts() -> list[str]:
    """Return 200 mock non-English copyright and warranty lines."""
    base_templates = [
        "Esta licencia aplica a este software.",
        "Ce logiciel est sous licence libre.",
        "Diese Lizenz gilt für diese Software.",
        "Questo software è fornito così com'è.",
        "このソフトウェアはオープンソースです。",
        "Este software é fornecido sem qualquer garantia explícita ou implícita.",
        "Данная программа является свободным программным обеспечением.",
        "本软件按“原样”提供，不带有任何明示或暗示的担保。",
        "Derechos de autor reservados. Consulte el archivo LICENSE para más detalles.",
        "Copyright (c) Tous droits réservés. Voir le fichier de licence.",
        "本プログラムは、現状のまま提供され、いかなる保証もありません。",
        "Program ten jest wolnym oprogramowaniem; możesz go rozprowadzać dalej.",
        "Tämä ohjelmisto toimitetaan sellaisenaan ilman takuuta.",
        "Denna programvara tillhandahålls i befintligt skick.",
        "Dit is vrije software, en je bent vrij om het te verspreiden.",
        "Bu yazılım, hiçbir garanti olmaksızın 'olduğu gibi' sağlanır.",
        "Tento software je poskytován tak, jak je.",
        "Ez a szoftver nyílt forráskódú.",
        "Acest software este furnizat ca atare.",
        "Цей продукт є відкритим програмним забезпеченням.",
        "이 소프트웨어는 오픈 소스입니다.",
    ]
    years = ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    authors = [
        "The Project Authors",
        "Contributors",
        "Open Source Initiative",
        "Free Software Foundation",
        "Acme Corp",
        "John Doe",
        "Jane Smith",
    ]

    texts = set(base_templates)
    while len(texts) < 200:
        year = random.choice(years)
        author = random.choice(authors)
        t_type = random.choice(
            [
                f"Copyright (c) {year} {author}. All rights reserved.",
                f"Copyright {year} {author}. " + random.choice(base_templates),
                f"Derechos de autor (c) {year} {author}.",
                f"Droits d'auteur {year} {author}.",
                f"Urheberrecht (c) {year} {author}.",
                f"저작권 (c) {year} {author}.",
                f"版权所有 (c) {year} {author}.",
            ]
        )
        texts.add(t_type)

    return list(texts)[:200]


FOREIGN_TEXTS = generate_foreign_texts()


def apply_casing(text: str) -> str:
    """Change the case of a text in one random way."""
    choice = random.choice(["upper", "lower", "camel", "random"])
    if choice == "upper":
        return text.upper()
    if choice == "lower":
        return text.lower()
    if choice == "camel":
        return re.sub(r"[^a-zA-Z0-9]+(.)", lambda m: m.group(1).upper(), text.lower())
    # random case
    return "".join(c.upper() if random.random() > 0.5 else c.lower() for c in text)


def drop_punct(text: str) -> str:
    """Drop or replace by a space one or two punctuation marks."""
    res = text
    puncts = ["-", ".", ",", "(", ")", ":"]
    for _ in range(random.randint(1, 2)):
        p = random.choice(puncts)
        res = res.replace(p, random.choice(["", " "]), 1)
    return res


def _drop_name_words(name: str) -> str:
    """Lower-case a name and drop its common filler words."""
    n = name.lower()
    if "public" in n and "general" in n:
        n = n.replace(random.choice(["public", "general"]), "").strip()
    if "variant" in n:
        n = n.replace("variant", "").strip()
    if "license" in n:
        n = n.replace("license", "").strip()
    if n.endswith("generic"):
        n = n[:-7].strip()
    if "project" in n:
        n = n.replace("project", "").strip()
    return n


def _swap_spellings(name: str, n: str) -> str:
    """Swap licence/license and non/no in n, as `name` spells them."""
    if "licence" in name.lower():
        n = re.sub(r"(?i)licence", "license", n)
    elif "license" in name.lower():
        n = re.sub(r"(?i)license", "licence", n)

    if "non" in name.lower():
        n = re.sub(r"(?i)\bnon\b", "no", n)
    elif "no" in name.lower():
        n = re.sub(r"(?i)\bno\b", "non", n)
    return n


def _alter_precision(m: re.Match[str]) -> str:
    """Add or drop a trailing ".0" of a version number."""
    val = m.group(1)
    if len(val.split(".")) == 2:
        return val + ".0"
    if len(val.split(".")) == 3 and val.endswith(".0"):
        return val[:-2]
    return val


def distort_name(name: str) -> str:
    """Return a licence name as a person might write it."""
    n = _swap_spellings(name, _drop_name_words(name))

    n = re.sub(r"(?i)\bversion\b", random.choice(["ver", "v", "v.", ""]), n)

    # Insert version before standalone float
    n = re.sub(r"\b(\d+\.\d+)\b", r"v \1", n)
    n = re.sub(r"(?i)\b(v|ver|version)\s+v\b", r"\1", n)

    n = re.sub(r"\b(\d+\.\d+(?:\.\d+)?)\b", _alter_precision, n)
    return re.sub(r"\s+", " ", n).strip()


def _distort_word(words: list[str]) -> None:
    """Change one random word in place."""
    idx = random.randint(0, len(words) - 1)
    word_op = random.random()
    if word_op < 0.4:
        words.pop(idx)
    elif word_op < 0.7:
        w = list(words[idx])
        if len(w) > 2:
            i = random.randint(0, len(w) - 2)
            w[i], w[i + 1] = w[i + 1], w[i]
            words[idx] = "".join(w)
    elif word_op < 0.8:
        words[idx] += random.choice(string.punctuation)
    elif word_op < 0.9:
        word = words[idx]
        if len(word) > 3:
            split_idx = random.randint(1, len(word) - 1)
            char = random.choice([" ", "-"])
            words[idx] = word[:split_idx] + char + word[split_idx:]
    else:
        words[idx] = re.sub(r"[^\w\s]", "", words[idx])


def _distort_structure(words: list[str], paragraphs: list[str]) -> list[str]:
    """Drop a paragraph or insert a foreign line; return the words."""
    struct_op = random.random()
    if struct_op < 0.5 and len(paragraphs) > 2:
        idx = random.randint(0, len(paragraphs) - 1)
        paragraphs.pop(idx)
        return ("\n\n".join(paragraphs)).split()
    idx = random.randint(0, max(0, len(words) - 1))
    words.insert(idx, random.choice(FOREIGN_TEXTS))
    return words


def distort_text(text: str, rate_percent: int) -> str:
    """Return text with about rate_percent of its words disturbed."""
    if rate_percent == 0:
        return text

    words = text.split()
    if not words:
        return text

    num_ops = max(1, int(len(words) * (rate_percent / 100.0)))
    paragraphs = text.split("\n\n")

    for _ in range(num_ops):
        if not words:
            break

        op = random.random()

        if op < 0.6:
            _distort_word(words)
        elif op < 0.9 and rate_percent >= 5:
            words = _distort_structure(words, paragraphs)
        else:
            idx = random.randint(0, max(0, len(words) - 1))
            words.insert(idx, "\n")

    return " ".join(words)
