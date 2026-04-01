from __future__ import annotations

import argparse
import random
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


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_mst(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def sleep_between(min_delay: float, max_delay: float) -> None:
    wait_seconds = random.uniform(min_delay, max_delay)
    time.sleep(wait_seconds)


def load_page_source(driver: webdriver.Chrome, url: str, min_delay: float, max_delay: float) -> str:
    driver.get(url)
    WebDriverWait(driver, 25).until(lambda d: d.execute_script("return document.readyState") == "complete")
    sleep_between(min_delay, max_delay)
    return driver.page_source


def find_first_visible(driver: webdriver.Chrome, selectors: list[str]):
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            try:
                if element.is_displayed() and element.is_enabled():
                    return element
            except Exception:
                continue
    return None


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
    WebDriverWait(driver, 25).until(lambda d: d.execute_script("return document.readyState") == "complete")
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

    WebDriverWait(driver, 25).until(lambda d: d.execute_script("return document.readyState") == "complete")
    sleep_between(min_delay, max_delay)
    return driver.page_source


def extract_first_masothue_detail_url(search_html: str, mst: str) -> str:
    soup = BeautifulSoup(search_html, "html.parser")
    mst_pattern = re.escape(mst)
    exact_re = re.compile(rf"^https://masothue\.com/{mst_pattern}(?:$|[-/].*)")

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        abs_href = href if href.startswith("http") else f"https://masothue.com{href}"
        if exact_re.match(abs_href):
            return abs_href

    # Fallback: accept any detail page that contains the MST token.
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        abs_href = href if href.startswith("http") else f"https://masothue.com{href}"
        if abs_href.startswith("https://masothue.com/") and mst in abs_href:
            return abs_href
    return ""


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


def parse_email_and_industry(page_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(page_html, "html.parser")
    plain_text = soup.get_text("\n", strip=True)
    lines = [normalize_space(line) for line in plain_text.splitlines() if normalize_space(line)]

    email = ""
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", plain_text)
    if email_match:
        email = normalize_space(email_match.group(0))

    industry = parse_lines_by_aliases(
        lines,
        [
            "Ngành nghề chính",
            "Ngành nghề kinh doanh",
            "Ngành nghề",
            "Ngành nghề KD chính",
        ],
    )

    return email, industry


def lookup_masothue(driver: webdriver.Chrome, mst: str, min_delay: float, max_delay: float) -> dict[str, str]:
    search_url = "https://masothue.com/"
    try:
        search_html = search_via_input(
            driver=driver,
            start_url=search_url,
            query=mst,
            input_selectors=[
                "input[name='q']",
                "input[type='search']",
                "input[placeholder*='mã số thuế']",
                "input[placeholder*='Mã số thuế']",
                "form input[type='text']",
            ],
            submit_selectors=[
                "button[type='submit']",
                "input[type='submit']",
                "form button",
            ],
            min_delay=min_delay,
            max_delay=max_delay,
        )
        detail_url = extract_first_masothue_detail_url(search_html, mst)
        if not detail_url:
            return {"url": search_url, "email": "", "industry": "", "status": "not_found"}

        detail_html = load_page_source(driver, detail_url, min_delay=min_delay, max_delay=max_delay)
        email, industry = parse_email_and_industry(detail_html)
        return {
            "url": detail_url,
            "email": email,
            "industry": industry,
            "status": "ok" if (email or industry) else "ok_but_empty",
        }
    except Exception as error:  # noqa: BLE001
        return {"url": search_url, "email": "", "industry": "", "status": f"error:{error.__class__.__name__}"}


def extract_first_tvpl_detail_url(search_html: str, mst: str) -> str:
    soup = BeautifulSoup(search_html, "html.parser")
    # Typical form: /ma-so-thue/<slug>-mst-0319459101.html
    pattern = re.compile(rf"/ma-so-thue/[^\"\s>]*-mst-{re.escape(mst)}\.html", flags=re.IGNORECASE)

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if pattern.search(href):
            if href.startswith("http"):
                return href
            return f"https://thuvienphapluat.vn{href}"
    return ""


def lookup_tvpl(driver: webdriver.Chrome, mst: str, min_delay: float, max_delay: float) -> dict[str, str]:
    search_url = "https://thuvienphapluat.vn/ma-so-thue"
    try:
        search_html = search_via_input(
            driver=driver,
            start_url=search_url,
            query=mst,
            input_selectors=[
                "input[name='keyword']",
                "input[name='q']",
                "input[id*='keyword']",
                "input[type='search']",
                "form input[type='text']",
            ],
            submit_selectors=[
                "button[type='submit']",
                "input[type='submit']",
                "form button",
            ],
            min_delay=min_delay,
            max_delay=max_delay,
        )
        detail_url = extract_first_tvpl_detail_url(search_html, mst)
        if not detail_url:
            return {"url": search_url, "email": "", "industry": "", "status": "not_found"}

        detail_html = load_page_source(driver, detail_url, min_delay=min_delay, max_delay=max_delay)
        email, industry = parse_email_and_industry(detail_html)
        return {
            "url": detail_url,
            "email": email,
            "industry": industry,
            "status": "ok" if (email or industry) else "ok_but_empty",
        }
    except Exception as error:  # noqa: BLE001
        return {"url": search_url, "email": "", "industry": "", "status": f"error:{error.__class__.__name__}"}


def pick_sample_rows(input_file: Path, sample_size: int) -> pd.DataFrame:
    df = pd.read_excel(input_file)
    mst_col = "Mã số thuế" if "Mã số thuế" in df.columns else "ma_so_thue"
    name_col = "Tên Tiếng Việt" if "Tên Tiếng Việt" in df.columns else "ten_tieng_viet"

    work = df.copy()
    work[mst_col] = work[mst_col].astype(str).map(normalize_mst)
    work = work[(work[mst_col] != "") & (work[mst_col].str.lower() != "nan")]
    work = work.drop_duplicates(subset=[mst_col], keep="last")
    return work[[name_col, mst_col]].tail(sample_size).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample enrich email/industry by MST from masothue + thuvienphapluat")
    parser.add_argument(
        "--input-file",
        type=str,
        default="output/hsctvn_feb2026_all_pages_merged.xlsx",
        help="Merged input Excel path",
    )
    parser.add_argument("--sample-size", type=int, default=5, help="How many tail companies to test")
    parser.add_argument("--min-delay", type=float, default=2.5, help="Min delay seconds between requests")
    parser.add_argument("--max-delay", type=float, default=4.5, help="Max delay seconds between requests")
    parser.add_argument(
        "--output-file",
        type=str,
        default="output/mst_enrich_sample_result.xlsx",
        help="Output result Excel path",
    )
    args = parser.parse_args()

    input_file = Path(args.input_file)
    output_file = Path(args.output_file)
    sample_df = pick_sample_rows(input_file=input_file, sample_size=max(1, args.sample_size))

    driver = build_driver()
    results: list[dict[str, str]] = []
    try:
        for i, row in sample_df.iterrows():
            company_name = str(row.iloc[0])
            mst = normalize_mst(str(row.iloc[1]))
            print(f"[{i+1}/{len(sample_df)}] lookup MST={mst} | {company_name}")

            masothue_data = lookup_masothue(driver, mst=mst, min_delay=args.min_delay, max_delay=args.max_delay)
            tvpl_data = lookup_tvpl(driver, mst=mst, min_delay=args.min_delay, max_delay=args.max_delay)

            # Prefer masothue when available; fallback to TVPL.
            mapped_email = masothue_data["email"] or tvpl_data["email"]
            mapped_industry = masothue_data["industry"] or tvpl_data["industry"]

            results.append(
                {
                    "ten_tieng_viet": company_name,
                    "ma_so_thue": mst,
                    "mapped_email": mapped_email,
                    "mapped_nganh_nghe": mapped_industry,
                    "masothue_status": masothue_data["status"],
                    "masothue_url": masothue_data["url"],
                    "masothue_email": masothue_data["email"],
                    "masothue_nganh_nghe": masothue_data["industry"],
                    "tvpl_status": tvpl_data["status"],
                    "tvpl_url": tvpl_data["url"],
                    "tvpl_email": tvpl_data["email"],
                    "tvpl_nganh_nghe": tvpl_data["industry"],
                }
            )
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    result_df = pd.DataFrame(results)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_excel(output_file, index=False)

    filled_email = int(result_df["mapped_email"].fillna("").astype(str).str.strip().ne("").sum())
    filled_nganh = int(result_df["mapped_nganh_nghe"].fillna("").astype(str).str.strip().ne("").sum())
    print(f"Saved sample result: {output_file}")
    print(f"Rows tested: {len(result_df)}")
    print(f"Rows mapped email: {filled_email}")
    print(f"Rows mapped nganh_nghe: {filled_nganh}")


if __name__ == "__main__":
    main()
