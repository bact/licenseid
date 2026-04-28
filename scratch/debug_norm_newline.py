from licenseid.normalize import normalize_text

t = "Apache License\nVersion 2.0"
norm = normalize_text(t)
print(f"Original: {repr(t)}")
print(f"Normalized: {repr(norm)}")
print(f"Words: {norm.split()}")
