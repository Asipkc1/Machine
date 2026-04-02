from __future__ import annotations

import re
import unicodedata

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

INDUSTRIAL_ZONE_PATTERN = (
    r"khu\s*c[oô]ng\s*nghi[ẹeệ]p|\bkcn\b|\bkhu\s*cn\b|"
    r"c[ụu]m\s*c[oô]ng\s*nghi[ẹeệ]p|\bccn\b|"
    r"khu\s*ch[ếe]\s*xu[ấa]t|\bkcx\b|"
    r"khu\s*kinh\s*t[ếe]|\bindustrial\s*park\b|"
    r"c[oô]ng\s*nghi[ẹeệ]p|cong\s*nghiep|\bcn\b|"
    r"khu\s*c[oô]ng\s*ngh[eệ]|\bkcnc\b"
)


def build_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver with standard options."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_argument(f"user-agent={USER_AGENT}")
    return webdriver.Chrome(options=options)


def address_matches_industrial_zone(address: str) -> bool:
    """Check if address text matches industrial-zone keywords."""
    # Normalize to NFC first so precomposed Vietnamese chars (e.g. ệ U+1EC7)
    # match regardless of whether the source text is NFC or NFD encoded.
    normalized = unicodedata.normalize("NFC", address or "")
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    if not normalized:
        return False
    return bool(re.search(INDUSTRIAL_ZONE_PATTERN, normalized))
