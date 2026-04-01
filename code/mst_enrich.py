from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from shared import build_driver

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT_DIR / "output" / "hsctvn_feb2026_all_pages_merged.xlsx"
DEFAULT_OUTPUT = ROOT_DIR / "output" / "hsctvn_feb2026_enriched.xlsx"
CHECKPOINT_FILE = ROOT_DIR / "output" / ".enrich_checkpoint.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_mst(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def sleep_between(min_delay: float, max_delay: float) -> None:
    import random
    time.sleep(random.uniform(min_delay, max_delay))


def find_first_visible(driver: webdriver.Chrome, selectors: list[str]):
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for el in elements:
            try:
                if el.is_displayed() and el.is_enabled():
                    return el
            except Exception:
                continue
    return None


def load_page_source(driver: webdriver.Chrome, url: str, min_delay: float, max_delay: float) -> str:
    driver.get(url)
    WebDriverWait(driver, 25).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    sleep_between(min_delay, max_delay)
    return driver.page_source


def search_via_input(
    driver: webdriver.Chrome,
    start_url: str,
    query: str,
    input_selectors: list[str],
    submit_selectors: list[str],
    min_delay: float,
    max_delay: float,
) -> str:
    driver.get(start_url)
    WebDriverWait(driver, 25).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    sleep_between(min_delay, max_delay)

    search_input = find_first_visible(driver, input_selectors)
    if search_input is None:
        raise RuntimeError("search_input_not_found")

    search_input.clear()
    search_input.send_keys(query)
    sleep_between(0.4, 0.8)

    submit_button = find_first_visible(driver, submit_selectors)
    if submit_button is not None:
        submit_button.click()
    else:
        search_input.send_keys(Keys.ENTER)

    WebDriverWait(driver, 25).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    sleep_between(min_delay, max_delay)
    return driver.page_source


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_lines_by_aliases(lines: list[str], aliases: list[str]) -> str:
    for idx, line in enumerate(lines):
        for alias in aliases:
            match = re.search(rf"{re.escape(alias)}\s*:?\s*(.*)$", line, flags=re.IGNORECASE)
            if not match:
                continue
            value = normalize_space(match.group(1))
            if value:
                return value
            if idx + 1 < len(lines):
                next_line = normalize_space(lines[idx + 1])
                if next_line and ":" not in next_line:
                    return next_line
    return ""


def parse_detail_fields(page_html: str) -> dict[str, str]:
    """Extract industry, charter capital, and email from a detail page."""
    soup = BeautifulSoup(page_html, "html.parser")
    plain_text = soup.get_text("\n", strip=True)
    lines = [normalize_space(l) for l in plain_text.splitlines() if normalize_space(l)]

    email = ""
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", plain_text)
    if email_match:
        email = normalize_space(email_match.group(0))

    industry = parse_lines_by_aliases(lines, [
        "Ngành nghề chính",
        "Ngành nghề kinh doanh",
        "Ngành nghề KD chính",
        "Ngành nghề",
    ])

    capital = parse_lines_by_aliases(lines, [
        "Vốn điều lệ",
        "Vốn Điều Lệ",
        "Von dieu le",
    ])

    return {"email": email, "industry": industry, "capital": capital}


# ---------------------------------------------------------------------------
# masothue.com
# ---------------------------------------------------------------------------

def _extract_masothue_detail_url(search_html: str, mst: str) -> str:
    soup = BeautifulSoup(search_html, "html.parser")
    mst_pat = re.escape(mst)
    exact_re = re.compile(rf"^https://masothue\.com/{mst_pat}(?:$|[-/].*)")

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        abs_href = href if href.startswith("http") else f"https://masothue.com{href}"
        if exact_re.match(abs_href):
            return abs_href

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        abs_href = href if href.startswith("http") else f"https://masothue.com{href}"
        if abs_href.startswith("https://masothue.com/") and mst in abs_href:
            return abs_href
    return ""


def lookup_masothue(
    driver: webdriver.Chrome, mst: str, min_delay: float, max_delay: float,
) -> dict[str, str]:
    search_url = "https://masothue.com/"
    try:
        search_html = search_via_input(
            driver=driver, start_url=search_url, query=mst,
            input_selectors=[
                "input[name='q']", "input[type='search']",
                "input[placeholder*='mã số thuế']", "form input[type='text']",
            ],
            submit_selectors=["button[type='submit']", "input[type='submit']", "form button"],
            min_delay=min_delay, max_delay=max_delay,
        )
        detail_url = _extract_masothue_detail_url(search_html, mst)
        if not detail_url:
            return {"status": "not_found", "email": "", "industry": "", "capital": ""}

        detail_html = load_page_source(driver, detail_url, min_delay, max_delay)
        fields = parse_detail_fields(detail_html)
        fields["status"] = "ok" if any(fields.values()) else "ok_but_empty"
        return fields
    except Exception as e:
        return {"status": f"error:{e.__class__.__name__}", "email": "", "industry": "", "capital": ""}


# ---------------------------------------------------------------------------
# thuvienphapluat.vn
# ---------------------------------------------------------------------------

def _extract_tvpl_detail_url(search_html: str, mst: str) -> str:
    soup = BeautifulSoup(search_html, "html.parser")
    pattern = re.compile(
        rf"/ma-so-thue/[^\"\s>]*-mst-{re.escape(mst)}\.html", flags=re.IGNORECASE
    )
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if pattern.search(href):
            return href if href.startswith("http") else f"https://thuvienphapluat.vn{href}"
    return ""


def lookup_tvpl(
    driver: webdriver.Chrome, mst: str, min_delay: float, max_delay: float,
) -> dict[str, str]:
    search_url = "https://thuvienphapluat.vn/ma-so-thue"
    try:
        search_html = search_via_input(
            driver=driver, start_url=search_url, query=mst,
            input_selectors=[
                "input[name='keyword']", "input[name='q']",
                "input[id*='keyword']", "input[type='search']", "form input[type='text']",
            ],
            submit_selectors=["button[type='submit']", "input[type='submit']", "form button"],
            min_delay=min_delay, max_delay=max_delay,
        )
        detail_url = _extract_tvpl_detail_url(search_html, mst)
        if not detail_url:
            return {"status": "not_found", "email": "", "industry": "", "capital": ""}

        detail_html = load_page_source(driver, detail_url, min_delay, max_delay)
        fields = parse_detail_fields(detail_html)
        fields["status"] = "ok" if any(fields.values()) else "ok_but_empty"
        return fields
    except Exception as e:
        return {"status": f"error:{e.__class__.__name__}", "email": "", "industry": "", "capital": ""}


# ---------------------------------------------------------------------------
# Checkpoint (resume support)
# ---------------------------------------------------------------------------

def load_checkpoint(path: Path) -> dict[str, dict[str, str]]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_checkpoint(path: Path, data: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main enrich logic
# ---------------------------------------------------------------------------

def enrich(
    input_file: Path,
    output_file: Path,
    checkpoint_file: Path,
    min_delay: float,
    max_delay: float,
    save_every: int,
) -> None:
    df = pd.read_excel(input_file)
    mst_col = "Mã số thuế" if "Mã số thuế" in df.columns else "ma_so_thue"

    df["_mst_clean"] = df[mst_col].astype(str).map(normalize_mst)
    valid_mask = (df["_mst_clean"] != "") & (df["_mst_clean"].str.lower() != "nan")
    unique_msts = df.loc[valid_mask, "_mst_clean"].drop_duplicates().tolist()

    checkpoint = load_checkpoint(checkpoint_file)
    remaining = [m for m in unique_msts if m not in checkpoint]

    print(f"Tong MST duy nhat: {len(unique_msts)}")
    print(f"Da co trong checkpoint: {len(checkpoint)}")
    print(f"Can xu ly tiep: {len(remaining)}")

    if not remaining:
        print("Tat ca MST da duoc enrich.")
    else:
        driver = build_driver()
        try:
            for i, mst in enumerate(remaining, 1):
                print(f"[{i}/{len(remaining)}] MST={mst}")

                mt = lookup_masothue(driver, mst, min_delay, max_delay)
                tv = lookup_tvpl(driver, mst, min_delay, max_delay)

                result = {
                    "industry": mt["industry"] or tv["industry"],
                    "capital": mt["capital"] or tv["capital"],
                    "email": mt["email"] or tv["email"],
                    "masothue_status": mt["status"],
                    "tvpl_status": tv["status"],
                }
                checkpoint[mst] = result

                if i % save_every == 0:
                    save_checkpoint(checkpoint_file, checkpoint)
                    print(f"  -> Checkpoint saved ({len(checkpoint)}/{len(unique_msts)})")
        except KeyboardInterrupt:
            print("\nBi ngat! Dang luu checkpoint...")
        finally:
            save_checkpoint(checkpoint_file, checkpoint)
            print(f"Checkpoint saved: {len(checkpoint)}/{len(unique_msts)}")
            try:
                driver.quit()
            except Exception:
                pass

    # Map enriched data back to dataframe
    df["Ngành nghề (enrich)"] = df["_mst_clean"].map(
        lambda m: checkpoint.get(m, {}).get("industry", "")
    )
    df["Vốn điều lệ (enrich)"] = df["_mst_clean"].map(
        lambda m: checkpoint.get(m, {}).get("capital", "")
    )
    df["Email (enrich)"] = df["_mst_clean"].map(
        lambda m: checkpoint.get(m, {}).get("email", "")
    )
    df.drop(columns=["_mst_clean"], inplace=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_file, index=False)
    print(f"File ket qua: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich company data with industry & charter capital via MST lookup"
    )
    parser.add_argument("--input-file", type=str, default=str(DEFAULT_INPUT))
    parser.add_argument("--output-file", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--checkpoint-file", type=str, default=str(CHECKPOINT_FILE))
    parser.add_argument("--min-delay", type=float, default=2.5, help="Min delay (seconds)")
    parser.add_argument("--max-delay", type=float, default=4.5, help="Max delay (seconds)")
    parser.add_argument("--save-every", type=int, default=10, help="Save checkpoint every N lookups")
    args = parser.parse_args()

    enrich(
        input_file=Path(args.input_file),
        output_file=Path(args.output_file),
        checkpoint_file=Path(args.checkpoint_file),
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        save_every=args.save_every,
    )
