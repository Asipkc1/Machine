"""Test parse detail fields from masothue.com and thuvienphapluat.vn"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import re
import time

MST = "0100107518"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--disable-gpu")
opts.add_argument("--no-sandbox")
opts.add_argument("--window-size=1920,1080")
opts.add_argument("--log-level=3")
opts.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)


def normalize_space(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_field(lines, aliases):
    for idx, line in enumerate(lines):
        for alias in aliases:
            m = re.search(rf"{re.escape(alias)}\s*:?\s*(.*)$", line, re.IGNORECASE)
            if not m:
                continue
            val = normalize_space(m.group(1))
            if val:
                return val
            if idx + 1 < len(lines):
                nxt = normalize_space(lines[idx + 1])
                if nxt and ":" not in nxt:
                    return nxt
    return ""


driver = webdriver.Chrome(options=opts)
try:
    # =============================================
    # masothue.com — Detail page
    # =============================================
    print("=== masothue.com DETAIL ===")
    # JS submit to get to detail page
    driver.get("https://masothue.com/")
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(2)

    js_submit = (
        "var inp = document.querySelector('input[name=\"q\"]');"
        "if (!inp) return 'no_input';"
        "inp.value = arguments[0];"
        "var form = inp.closest('form');"
        "if (form) { form.submit(); return 'form_submitted'; }"
        "return 'no_form';"
    )
    driver.execute_script(js_submit, MST)
    time.sleep(5)
    detail_url = driver.current_url
    print(f"Detail URL: {detail_url}")

    body = driver.page_source
    soup = BeautifulSoup(body, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [normalize_space(l) for l in text.split("\n") if normalize_space(l)]

    # Print all lines containing key fields
    for kw in ["Vốn điều lệ", "Ngành nghề", "Email", "Loại hình", "Đại diện", "Ngày cấp", "Trạng thái"]:
        for i, line in enumerate(lines):
            if kw.lower() in line.lower():
                ctx = lines[max(0, i-1):i+3]
                print(f"  [{kw}] context:")
                for c in ctx:
                    print(f"    {c[:150]}")
                break

    # Try extracting
    industry = extract_field(lines, ["Ngành nghề chính", "Ngành nghề kinh doanh", "Ngành nghề"])
    capital = extract_field(lines, ["Vốn điều lệ"])
    print(f"\n  Parsed industry: {industry!r}")
    print(f"  Parsed capital: {capital!r}")

    # =============================================
    # thuvienphapluat.vn — Search + Detail
    # =============================================
    print("\n=== thuvienphapluat.vn SEARCH + DETAIL ===")
    search_url = f"https://thuvienphapluat.vn/ma-so-thue?keyword={MST}"
    driver.get(search_url)
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(3)

    body2 = driver.page_source
    # Find detail link
    pat = re.compile(rf"/ma-so-thue/[^\"\s>]*{MST}[^\"\s>]*\.html", re.I)
    detail_links = pat.findall(body2)
    if detail_links:
        detail_href = detail_links[0]
        if not detail_href.startswith("http"):
            detail_href = f"https://thuvienphapluat.vn{detail_href}"
        print(f"Detail link: {detail_href}")

        driver.get(detail_href)
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(3)
        print(f"Detail URL: {driver.current_url}")

        body3 = driver.page_source
        soup3 = BeautifulSoup(body3, "html.parser")
        text3 = soup3.get_text("\n", strip=True)
        lines3 = [normalize_space(l) for l in text3.split("\n") if normalize_space(l)]

        for kw in ["Vốn điều lệ", "Ngành nghề", "Email", "Đại diện", "Ngày cấp"]:
            for i, line in enumerate(lines3):
                if kw.lower() in line.lower():
                    ctx = lines3[max(0, i-1):i+3]
                    print(f"  [{kw}] context:")
                    for c in ctx:
                        print(f"    {c[:150]}")
                    break

        industry3 = extract_field(lines3, ["Ngành nghề chính", "Ngành nghề kinh doanh", "Ngành nghề"])
        capital3 = extract_field(lines3, ["Vốn điều lệ"])
        print(f"\n  Parsed industry: {industry3!r}")
        print(f"  Parsed capital: {capital3!r}")
    else:
        print("  No detail link found!")

finally:
    driver.quit()

print("\nDONE")
