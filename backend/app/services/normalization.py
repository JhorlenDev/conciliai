import re
import unicodedata

from rapidfuzz.fuzz import ratio


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFD", value.upper())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    tokens = re.sub(r"[^A-Z0-9 ]", " ", value).split()
    return " ".join(token for token in tokens if token not in {"DE", "DA", "DO", "DAS", "DOS"})


def normalize_statement_nature(value: str | None) -> str:
    """Presents bank statement direction consistently, including legacy values."""
    normalized = normalize_name(value or "")
    if normalized in {"C", "CREDITO", "ENTRADA"}:
        return "Crédito"
    if normalized in {"D", "DEBITO", "SAIDA"}:
        return "Débito"
    return ""


def accounting_nature(value: str | None) -> str:
    nature = normalize_statement_nature(value)
    return "Débito" if nature == "Crédito" else "Crédito" if nature == "Débito" else ""


def is_statement_debit(value: str | None) -> bool:
    return normalize_statement_nature(value) == "Débito"


def normalize_rule_accounting_nature(value: str | None) -> str:
    # Rules saved before the visual change stored the statement direction.
    normalized = normalize_name(value or "")
    if normalized == "SAIDA":
        return "Crédito"
    if normalized == "ENTRADA":
        return "Débito"
    return normalize_statement_nature(value)


def names_similar(left: str, right: str, allow_truncated_terminal: bool = False) -> bool:
    a, b = normalize_name(left).split(), normalize_name(right).split()
    if not a or not b:
        return False
    compatible = lambda first, second: first.startswith(second) or second.startswith(first)
    if not compatible(a[0], b[0]):
        return False
    terminal_matches = compatible(a[-1], b[-1])
    if not terminal_matches and not allow_truncated_terminal:
        return False
    # Match abbreviated middle names in order, for example C F -> COLARES FRAZAO.
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    position = 1
    tokens_to_match = shorter[1:] if not terminal_matches else shorter[1:-1]
    for token in tokens_to_match:
        match_index = next((index for index in range(position, len(longer) - 1) if compatible(token, longer[index])), None)
        if match_index is None:
            return False
        position = match_index + 1
    if not terminal_matches:
        # Some PDF text extracts end before the final surname. The caller still
        # applies exact date, value, operation, nature, and time constraints.
        return len(a) != len(b) and position == len(shorter)
    expanded = []
    for token in a:
        expanded.append(next((candidate for candidate in b if candidate.startswith(token) or token.startswith(candidate)), token))
    return ratio(" ".join(expanded), " ".join(b)) >= 80
