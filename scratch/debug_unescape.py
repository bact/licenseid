

def unescape_text(text: str) -> str:
    try:
        return text.encode("utf-8").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError):
        return text


# Test case 1: literal backslash and n
t1 = "Apache\\nVersion"
print(f"Original: {t1}")
print(f"Unescaped: {repr(unescape_text(t1))}")

# Test case 2: real newline
t2 = "Apache\nVersion"
print(f"Original: {repr(t2)}")
print(f"Unescaped: {repr(unescape_text(t2))}")
