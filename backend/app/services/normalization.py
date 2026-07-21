import re
import unicodedata

from rapidfuzz.fuzz import ratio


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFD", value.upper())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    tokens = re.sub(r"[^A-Z0-9 ]", " ", value).split()
    return " ".join(token for token in tokens if token not in {"DE", "DA", "DO", "DAS", "DOS"})


def names_similar(left: str, right: str) -> bool:
    a, b = normalize_name(left).split(), normalize_name(right).split()
    if not a or not b:
        return False
    compatible = lambda first, second: first.startswith(second) or second.startswith(first)
    if not compatible(a[0], b[0]) or not compatible(a[-1], b[-1]):
        return False
    expanded = []
    for token in a:
        expanded.append(next((candidate for candidate in b if candidate.startswith(token) or token.startswith(candidate)), token))
    return ratio(" ".join(expanded), " ".join(b)) >= 80
