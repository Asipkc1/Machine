from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
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


def sleep_between(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# masothue.com – lookup via JS form.submit()
# ---------------------------------------------------------------------------

def _search_masothue(driver, mst: str, min_delay: float, max_delay: float) -> None:
    """Navigate to masothue.com detail page for *mst* using JS form submit."""
    driver.get("https://masothue.com/")
    WebDriverWait(driver, 20).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    sleep_between(min_delay, max_delay)
    driver.execute_script(
        "var inp = document.querySelector('input[name=\"q\"]');"
        "inp.value = arguments[0];"
        "inp.closest('form').submit();",
        mst,
    )
    WebDriverWait(driver, 20).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    sleep_between(min_delay, max_delay)


def _parse_masothue_detail(html: str) -> dict[str, str]:
    """Parse the masothue.com detail page for industry info."""
    soup = BeautifulSoup(html, "html.parser")

    # --- primary industry from "Ngành nghề chính" label ---
    industry = ""
    for tag in soup.find_all(string=re.compile(r"Ngành\s+nghề\s+chính", re.I)):
        parent = tag.find_parent()
        if parent is None:
            continue
        next_sib = parent.find_next_sibling()
        if next_sib:
            industry = normalize_space(next_sib.get_text())
            break
        # fallback: text after the label in same parent
        rest = normalize_space(tag).split(":", 1)
        if len(rest) == 2 and rest[1]:
            industry = rest[1]
            break

    # If not found, try table rows
    if not industry:
        for td in soup.select("table.table-taxinfo td"):
            txt = normalize_space(td.get_text())
            if re.search(r"Ngành\s+nghề\s+chính", txt, re.I):
                next_td = td.find_next_sibling("td")
                if next_td:
                    industry = normalize_space(next_td.get_text())
                    break

    # --- all registered industry codes (second table) ---
    industry_codes: list[str] = []
    for table in soup.select("table"):
        headers = [normalize_space(th.get_text()) for th in table.select("th")]
        if any("Mã" in h for h in headers) and any("Ngành" in h for h in headers):
            for row in table.select("tr")[1:]:
                cells = row.select("td")
                if len(cells) >= 2:
                    code = normalize_space(cells[0].get_text())
                    name = normalize_space(cells[1].get_text())
                    if code and name:
                        industry_codes.append(f"{code} - {name}")
            break

    return {
        "industry": industry,
        "industry_codes": "; ".join(industry_codes),
    }


def lookup_masothue(driver, mst: str, min_delay: float, max_delay: float) -> dict[str, str]:
    empty = {"status": "error", "industry": "", "industry_codes": ""}
    try:
        _search_masothue(driver, mst, min_delay, max_delay)

        # After JS submit the browser either lands on the detail page directly
        # (URL contains the MST) or a search-results page.
        current = driver.current_url
        if mst not in current:
            # Try to find the detail link in search results
            soup = BeautifulSoup(driver.page_source, "html.parser")
            link = soup.select_one(f'a[href*="/{mst}"]')
            if link is None:
                return {**empty, "status": "not_found"}
            href = link["href"]
            url = href if href.startswith("http") else f"https://masothue.com{href}"
            driver.get(url)
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            sleep_between(min_delay, max_delay)

        fields = _parse_masothue_detail(driver.page_source)
        status = "ok" if fields["industry"] or fields["industry_codes"] else "ok_but_empty"
        return {**fields, "status": status}
    except Exception as e:
        return {**empty, "status": f"error:{e.__class__.__name__}"}


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
                result = lookup_masothue(driver, mst, min_delay, max_delay)
                checkpoint[mst] = result
                print(f"  status={result['status']}  industry={result['industry'][:60]}")

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
    df["Ngành nghề chính (enrich)"] = df["_mst_clean"].map(
        lambda m: checkpoint.get(m, {}).get("industry", "")
    )
    df["Ngành nghề đăng ký (enrich)"] = df["_mst_clean"].map(
        lambda m: checkpoint.get(m, {}).get("industry_codes", "")
    )
    df.drop(columns=["_mst_clean"], inplace=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_file, index=False)
    print(f"File ket qua: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich company data with industry info from masothue.com"
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
