from __future__ import annotations

import argparse
import concurrent.futures
import random
import re
import threading
import time
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

BASE_LIST_URL = "https://hsctvn.com/thang-02/2026"
PAGE_URL_TEMPLATE = "https://hsctvn.com/thang-02/2026/page-{page}"
SITE_ROOT_URL = "https://hsctvn.com/"
OUTPUT_FILE_NAME = "cong_ty_thanh_lap_thang_02_2026_hsctvn.xlsx"
EXPECTED_MONTH = "02/2026"

# Conservative defaults to reduce the chance of being rate-limited/blocked.
DEFAULT_REQUESTS_PER_SECOND = 0.2
DEFAULT_MIN_INTERVAL_SECONDS = 0.7

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

FIELD_ALIASES = {
    "ten_tieng_anh": ["Tên tiếng Anh", "Tên quốc tế", "Tên giao dịch", "Tên viết tắt"],
    "ma_so_thue": ["Mã số thuế", "MST"],
    "dia_chi": ["Địa chỉ thuế", "Địa chỉ"],
    "nguoi_dai_dien": ["Đại diện pháp luật", "Người đại diện"],
    "dien_thoai": ["Điện thoại", "Số điện thoại"],
    "email": ["Email"],
    "nganh_nghe": ["Ngành nghề chính", "Ngành nghề kinh doanh", "Ngành nghề"],
    "ngay_cap": ["Ngày cấp", "Ngày hoạt động"],
    "trang_thai": ["Trạng thái"],
}


class RequestRateLimiter:
    """Thread-safe limiter that spaces outgoing requests."""

    def __init__(self, requests_per_second: float, min_interval_seconds: float) -> None:
        if requests_per_second <= 0:
            requests_per_second = 1.0
        self._interval = max(min_interval_seconds, 1.0 / requests_per_second)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                if now >= self._next_allowed:
                    self._next_allowed = now + self._interval
                    return
                wait_seconds = self._next_allowed - now
            if wait_seconds > 0:
                time.sleep(wait_seconds)


REQUEST_LIMITER = RequestRateLimiter(
    requests_per_second=DEFAULT_REQUESTS_PER_SECOND,
    min_interval_seconds=DEFAULT_MIN_INTERVAL_SECONDS,
)


def configure_rate_limit(requests_per_second: float, min_interval_seconds: float) -> None:
    """Reconfigure global request limiter from CLI args."""
    global REQUEST_LIMITER
    REQUEST_LIMITER = RequestRateLimiter(
        requests_per_second=requests_per_second,
        min_interval_seconds=min_interval_seconds,
    )


def build_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver for stable listing-page collection."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    return webdriver.Chrome(options=options)


def safe_quit(driver: webdriver.Chrome) -> None:
    """Quit browser without surfacing secondary cleanup errors."""
    try:
        driver.quit()
    except Exception:
        return


def fetch_html(url: str, retries: int = 3, timeout: int = 25) -> str:
    """Fetch HTML with retries and browser-like headers."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            REQUEST_LIMITER.acquire()
            request = Request(url=url, headers=HEADERS)
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.read().decode("utf-8", errors="ignore")
        except HTTPError as error:
            last_error = error
            if attempt < retries:
                retry_after = error.headers.get("Retry-After") if error.headers else None
                if retry_after and retry_after.isdigit():
                    delay = max(1.0, float(retry_after))
                elif error.code in {403, 429, 503}:
                    delay = (1.8**attempt) + random.uniform(0.3, 1.2)
                else:
                    delay = (0.8 * attempt) + random.uniform(0.1, 0.5)
                time.sleep(delay)
                continue
            break
        except (URLError, TimeoutError) as error:
            last_error = error
            if attempt < retries:
                time.sleep((0.8 * attempt) + random.uniform(0.1, 0.4))
                continue
            break
    raise RuntimeError(f"Cannot fetch URL: {url}") from last_error


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def address_matches_industrial_keywords(address: str) -> bool:
    """Match industrial-zone hints in address text."""
    normalized = normalize_space(address).lower()
    if not normalized:
        return False
    return bool(
        re.search(
            (
                r"khu\s*c[oô]ng\s*nghi[ẹe]p|\bkcn\b|\bkhu\s*cn\b|"
                r"c[ụu]m\s*c[oô]ng\s*nghi[ẹe]p|\bccn\b|"
                r"khu\s*ch[ếe]\s*xu[ấa]t|\bkcx\b|"
                r"khu\s*kinh\s*t[ếe]|\bindustrial\s*park\b|"
                r"c[oô]ng\s*nghi[ẹe]p|cong\s*nghiep|\bcn\b"
            ),
            normalized,
        )
    )


def parse_total_pages(first_page_html: str) -> int:
    """Infer total pagination pages from listing page links."""
    soup = BeautifulSoup(first_page_html, "html.parser")
    max_page = 1
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        match = re.search(r"/thang-02/2026/page-(\d+)", href)
        if match:
            page_num = int(match.group(1))
            if page_num > max_page:
                max_page = page_num
    return max_page


def detect_total_records(first_page_html: str) -> int | None:
    """Read the site-reported company count from the first page."""
    match = re.search(r"TÌM THẤY\s*([\d\.,]+)\s*HỒ SƠ CÔNG TY", first_page_html, flags=re.IGNORECASE)
    if not match:
        return None
    digits_only = re.sub(r"\D", "", match.group(1))
    return int(digits_only) if digits_only else None


def extract_listing_entries(page_html: str) -> list[dict[str, str]]:
    """Extract detail links and quick metadata from one listing page."""
    soup = BeautifulSoup(page_html, "html.parser")
    grouped: dict[str, dict[str, str]] = {}

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if not href:
            continue

        full_url = urljoin(SITE_ROOT_URL, href)
        if not full_url.endswith(".htm"):
            continue
        if "-com-" not in full_url:
            continue
        if "hsctvn.com" not in full_url:
            continue

        anchor_text = normalize_space(anchor.get_text(" ", strip=True))
        card_text = normalize_space(anchor.parent.get_text(" ", strip=True))
        address = ""
        tax_code = ""

        addr_match = re.search(r"Địa chỉ\s*:\s*(.*?)\s*Mã số thuế\s*:", card_text, flags=re.IGNORECASE)
        if addr_match:
            address = normalize_space(addr_match.group(1))

        tax_match = re.search(r"Mã số thuế\s*:\s*([0-9\-]+)", card_text, flags=re.IGNORECASE)
        if tax_match:
            tax_code = normalize_space(tax_match.group(1))

        current = grouped.setdefault(
            full_url,
            {
                "ten_tieng_viet": "",
                "detail_url": full_url,
                "dia_chi_listing": "",
                "ma_so_thue_listing": "",
            },
        )
        if anchor_text and not re.fullmatch(r"[0-9\-]+", anchor_text):
            if len(anchor_text) > len(current["ten_tieng_viet"]):
                current["ten_tieng_viet"] = anchor_text
        if address and not current["dia_chi_listing"]:
            current["dia_chi_listing"] = address
        if tax_code and not current["ma_so_thue_listing"]:
            current["ma_so_thue_listing"] = tax_code
        if not current["ma_so_thue_listing"] and re.fullmatch(r"[0-9\-]+", anchor_text):
            current["ma_so_thue_listing"] = anchor_text

    return [entry for entry in grouped.values() if entry["ten_tieng_viet"]]


def _looks_like_valid_listing_html(page_html: str) -> bool:
    """Detect whether the loaded page really contains HSCTVN listing content."""
    if "Danh sách công ty thành lập tháng 02/2026" not in page_html:
        return False
    if len(extract_listing_entries(page_html)) < 5:
        return False
    return True


def fetch_listing_html_with_selenium(driver: webdriver.Chrome, url: str, retries: int = 4) -> str:
    """Render a listing page in the browser and return validated listing HTML."""
    last_html = ""
    for attempt in range(1, retries + 1):
        REQUEST_LIMITER.acquire()
        driver.get(url)
        WebDriverWait(driver, 25).until(ec.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.0 + random.uniform(0.2, 0.9))
        last_html = driver.page_source
        if _looks_like_valid_listing_html(last_html):
            return last_html

        if attempt < retries:
            time.sleep((1.5 * attempt) + random.uniform(0.2, 0.8))

    return last_html


def _extract_value_by_aliases(lines: Iterable[str], aliases: list[str]) -> str:
    line_list = list(lines)
    for index, line in enumerate(line_list):
        for alias in aliases:
            pattern = rf"{re.escape(alias)}\s*:\s*(.*)$"
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue

            value = normalize_space(match.group(1))
            if value:
                return value

            # Some pages put the value in the next line after the label.
            if index + 1 < len(line_list):
                next_line = normalize_space(line_list[index + 1])
                if next_line and ":" not in next_line:
                    return next_line
    return ""


def parse_detail_page(detail_html: str, fallback_name: str) -> dict[str, str]:
    """Parse company detail page into normalized fields."""
    soup = BeautifulSoup(detail_html, "html.parser")

    h1 = soup.select_one("h1")
    ten_tieng_viet = normalize_space(h1.get_text(" ", strip=True) if h1 else fallback_name)

    plain_text = soup.get_text("\n", strip=True)
    lines = [normalize_space(line) for line in plain_text.splitlines() if normalize_space(line)]

    result = {
        "ten_tieng_viet": ten_tieng_viet,
        "ten_tieng_anh": _extract_value_by_aliases(lines, FIELD_ALIASES["ten_tieng_anh"]),
        "dia_chi": _extract_value_by_aliases(lines, FIELD_ALIASES["dia_chi"]),
        "ma_so_thue": _extract_value_by_aliases(lines, FIELD_ALIASES["ma_so_thue"]),
        "nguoi_dai_dien": _extract_value_by_aliases(lines, FIELD_ALIASES["nguoi_dai_dien"]),
        "dien_thoai": _extract_value_by_aliases(lines, FIELD_ALIASES["dien_thoai"]),
        "email": _extract_value_by_aliases(lines, FIELD_ALIASES["email"]),
        "nganh_nghe": _extract_value_by_aliases(lines, FIELD_ALIASES["nganh_nghe"]),
        "ngay_cap": _extract_value_by_aliases(lines, FIELD_ALIASES["ngay_cap"]),
        "trang_thai": _extract_value_by_aliases(lines, FIELD_ALIASES["trang_thai"]),
    }

    if not result["ma_so_thue"]:
        tax_match = re.search(r"Mã số thuế\s*[:\-]?\s*([0-9\-]+)", plain_text, flags=re.IGNORECASE)
        if tax_match:
            result["ma_so_thue"] = normalize_space(tax_match.group(1))

    result["thuoc_thang_02_2026"] = "yes" if result["ngay_cap"].endswith(EXPECTED_MONTH) else "no"

    return result


def collect_listing_entries(
    max_pages: int | None = None,
    start_page: int = 1,
    end_page: int | None = None,
) -> tuple[list[dict[str, str]], int, int | None]:
    driver = build_driver()
    try:
        first_html = fetch_listing_html_with_selenium(driver, BASE_LIST_URL)
        total_pages = parse_total_pages(first_html)
        total_records = detect_total_records(first_html)

        effective_end_page = total_pages
        if max_pages is not None:
            effective_end_page = min(effective_end_page, max_pages)
        if end_page is not None:
            effective_end_page = min(effective_end_page, end_page)
        effective_start_page = max(1, start_page)

        all_entries: list[dict[str, str]] = []
        for page_num in range(effective_start_page, effective_end_page + 1):
            try:
                if page_num == 1:
                    html = first_html
                else:
                    page_url = PAGE_URL_TEMPLATE.format(page=page_num)
                    html = fetch_listing_html_with_selenium(driver, page_url)

                entries = extract_listing_entries(html)
                for entry in entries:
                    entry["listing_page"] = str(page_num)
                all_entries.extend(entries)

                if page_num == effective_start_page or page_num % 25 == 0 or page_num == effective_end_page:
                    print(
                        f"Da doc listing den trang {page_num}/{effective_end_page}, "
                        f"tong link gom duoc: {len(all_entries)}"
                    )
            except Exception as error:  # noqa: BLE001
                print(f"Khong doc duoc listing page {page_num}: {error}")

        unique_by_url: dict[str, dict[str, str]] = {}
        for item in all_entries:
            unique_by_url[item["detail_url"]] = item

        return list(unique_by_url.values()), total_pages, total_records
    finally:
        safe_quit(driver)


def _safe_parse_company(entry: dict[str, str]) -> dict[str, str]:
    detail_url = entry["detail_url"]
    try:
        detail_html = fetch_html(detail_url)
        info = parse_detail_page(detail_html, fallback_name=entry["ten_tieng_viet"])
    except Exception as error:  # noqa: BLE001
        info = {
            "ten_tieng_viet": entry["ten_tieng_viet"],
            "ten_tieng_anh": "",
            "dia_chi": "",
            "ma_so_thue": "",
            "nguoi_dai_dien": "",
            "dien_thoai": "",
            "email": "",
            "nganh_nghe": "",
            "ngay_cap": "",
            "trang_thai": "",
        }
        info["ghi_chu"] = f"detail_error:{error.__class__.__name__}"

    if not info.get("ma_so_thue"):
        info["ma_so_thue"] = entry.get("ma_so_thue_listing", "")
    if not info.get("dia_chi"):
        info["dia_chi"] = entry.get("dia_chi_listing", "")

    info["detail_url"] = detail_url
    info["listing_page"] = entry.get("listing_page", "")
    info.setdefault("ghi_chu", "")
    return info


def collect_company_details(entries: list[dict[str, str]], workers: int = 12) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    total = len(entries)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(_safe_parse_company, entry): entry for entry in entries}
        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            rows.append(future.result())
            completed += 1
            if completed % 250 == 0 or completed == total:
                print(f"Da xu ly detail: {completed}/{total}")

    rows.sort(key=lambda item: (item.get("ma_so_thue", ""), item.get("ten_tieng_viet", "")))
    return rows


def export_excel(rows: list[dict[str, str]], output_path: Path) -> None:
    columns = [
        "ten_tieng_viet",
        "ten_tieng_anh",
        "ma_so_thue",
        "dia_chi",
        "nguoi_dai_dien",
        "dien_thoai",
        "email",
        "ngay_cap",
        "listing_page",
        "detail_url",
        "ghi_chu",
    ]
    dataframe = pd.DataFrame(rows)
    for column in columns:
        if column not in dataframe.columns:
            dataframe[column] = ""

    dataframe = dataframe[columns]
    dataframe = dataframe.rename(
        columns={
            "ten_tieng_viet": "Tên Tiếng Việt",
            "ten_tieng_anh": "Tên Tiếng Anh",
            "ma_so_thue": "Mã số thuế",
            "dia_chi": "Địa chỉ",
            "nguoi_dai_dien": "Người đại diện",
            "dien_thoai": "Điện thoại",
            "email": "Email",
            "ngay_cap": "Ngày cấp",
            "listing_page": "Trang listing",
            "detail_url": "Link chi tiết",
            "ghi_chu": "Ghi chú",
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_excel(output_path, index=False)


def run(
    max_pages: int | None = None,
    workers: int = 1,
    start_page: int = 1,
    end_page: int | None = None,
    requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
) -> Path:
    configure_rate_limit(
        requests_per_second=requests_per_second,
        min_interval_seconds=min_interval_seconds,
    )

    root_dir = Path(__file__).resolve().parent.parent
    output_path = root_dir / "output" / OUTPUT_FILE_NAME

    entries, total_pages, total_records = collect_listing_entries(
        max_pages=max_pages,
        start_page=start_page,
        end_page=end_page,
    )

    # Keep entries with industrial hints on listing address; keep empty-address entries
    # for detail verification to avoid missing true positives.
    prefiltered_entries: list[dict[str, str]] = []
    skipped_by_listing_filter = 0
    for entry in entries:
        listing_address = normalize_space(entry.get("dia_chi_listing", ""))
        if not listing_address:
            prefiltered_entries.append(entry)
            continue
        if address_matches_industrial_keywords(listing_address):
            prefiltered_entries.append(entry)
            continue
        skipped_by_listing_filter += 1

    print(f"Tong link cong ty gom duoc: {len(entries)}")
    print(f"So link bo qua theo loc dia chi listing: {skipped_by_listing_filter}")
    print(f"So link can vao trang chi tiet: {len(prefiltered_entries)}")
    print(f"Tong so trang site hien thi: {total_pages}")
    if total_records is not None:
        print(f"Tong ho so site cong bo: {total_records}")

    rows = collect_company_details(entries=prefiltered_entries, workers=workers)
    valid_rows = [row for row in rows if row.get("thuoc_thang_02_2026") == "yes"]
    valid_rows.sort(key=lambda item: (item.get("ma_so_thue", ""), item.get("ten_tieng_viet", "")))
    print(f"So ho so xac nhan Ngay cap thuoc {EXPECTED_MONTH}: {len(valid_rows)}")

    export_excel(rows=valid_rows, output_path=output_path)
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export HSCTVN companies established in 02/2026 to Excel")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit number of listing pages to crawl")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers for detail pages")
    parser.add_argument("--start-page", type=int, default=1, help="Start listing page to crawl")
    parser.add_argument("--end-page", type=int, default=None, help="End listing page to crawl")
    parser.add_argument(
        "--rps",
        type=float,
        default=DEFAULT_REQUESTS_PER_SECOND,
        help="Global max requests per second across listing/detail fetches",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=DEFAULT_MIN_INTERVAL_SECONDS,
        help="Minimum seconds between outbound requests",
    )
    args = parser.parse_args()

    file_path = run(
        max_pages=args.max_pages,
        workers=args.workers,
        start_page=args.start_page,
        end_page=args.end_page,
        requests_per_second=args.rps,
        min_interval_seconds=args.min_interval,
    )
    print(f"Da xuat Excel: {file_path}")
