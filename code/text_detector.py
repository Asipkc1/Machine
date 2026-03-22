import re
import string

from audit_config import ENGLISH_HINTS, VIETNAMESE_CHARS


def clean_text(text: str) -> str:
    """Collapse whitespace and trim text."""
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_token(token: str) -> str:
    return token.strip(string.punctuation + "“”‘’…")


def _has_weird_prefix_token(text: str) -> bool:
    """Detect malformed mixed-case prefixes like gCác or JKết."""
    for raw in text.split():
        token = _strip_token(raw)
        if len(token) < 2:
            continue
        if token[0].islower() and token[1].isupper():
            return True
        if len(token) >= 3 and token[0].isupper() and token[1].isupper() and token[2].islower():
            return True
    return False


def _mostly_english(text: str) -> bool:
    words = re.findall(r"[A-Za-z]+", text)
    long_words = [word for word in words if len(word) >= 3]
    return len(long_words) >= 2


def _is_time_or_metric(text: str) -> bool:
    patterns = [
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d+h\b",
        r"\b\d+m\b",
        r"\b\d+\s*phut\b",
        r"\b\d+\s*thg\b",
        r"^\d+\s*nguoi\s*choi$",
        r"^\d+\s*bots?$",
        r"^\d+\s*van.*$",
    ]
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def _is_username_like(text: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_.-]{3,24}", text) is not None


def _is_variant_or_proper_name(text: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_.\-']+(\s+[A-Za-z0-9_.\-']+){0,2}", text) is not None


def should_ignore_candidate(text: str) -> bool:
    """Filter out likely non-UI strings such as usernames and time values."""
    cleaned = clean_text(text)
    if not cleaned:
        return True
    if _is_time_or_metric(cleaned):
        return True
    if _is_username_like(cleaned):
        return True
    return False


def looks_not_vietnamized(text: str) -> tuple[bool, str]:
    """Heuristic to detect potentially non-Vietnamese UI strings."""
    cleaned = clean_text(text)
    if should_ignore_candidate(cleaned):
        return False, "ignored_noise"

    if len(cleaned) < 3:
        return False, "too_short"
    if re.fullmatch(r"[\d\W_]+", cleaned):
        return False, "symbol_or_number"
    if _has_weird_prefix_token(cleaned):
        return True, "broken_prefix"

    words = re.findall(r"[A-Za-z]+", cleaned)
    if not words:
        return False, "no_latin_word"

    lowered = {word.lower() for word in words}
    matched = sorted(lowered.intersection(ENGLISH_HINTS))
    if matched:
        if _mostly_english(cleaned):
            return True, f"english_ui:{','.join(matched)}"
        return True, f"mixed_vi_en:{','.join(matched)}"

    only_basic_latin = re.fullmatch(r"[A-Za-z0-9 /+\-:().,!?@#%&'\"]+", cleaned) is not None
    has_vn_diacritic = re.search(
        r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệóòỏõọốồổỗộớờởỡợúùủũụứừửữựíìỉĩịýỳỷỹỵ]",
        cleaned,
    ) is not None
    if only_basic_latin and not has_vn_diacritic:
        if _is_variant_or_proper_name(cleaned):
            return False, "proper_name_or_variant"
        if _mostly_english(cleaned):
            return True, "latin_ui_probable_en"
        return False, "latin_but_not_ui"

    invalid_chars = re.search(rf"[^{VIETNAMESE_CHARS}\s\-:().,!?@#%&'/\"+]", cleaned)
    if invalid_chars:
        return True, "contains_weird_glyph"

    return False, "looks_ok"
