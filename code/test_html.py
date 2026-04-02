"""Inspect HTML structure of masothue.com detail + thuvienphapluat.vn search results"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
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

driver = webdriver.Chrome(options=opts)
try:
    # =============================================
    # masothue.com — Inspect detail page structure
    # =============================================
    print("=== masothue.com DETAIL HTML ===")
    driver.get("https://masothue.com/")
    WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(2)
    js_submit = (
        "var inp = document.querySelector('input[name=\"q\"]');"
        "if (!inp) return 'no_input';"
        "inp.value = arguments[0];"
        "var form = inp.closest('form');"
        "if (form) { form.submit(); return 'ok'; }"
        "return 'no_form';"
    )
    driver.execute_script(js_submit, MST)
    time.sleep(6)
    print(f"URL: {driver.current_url}")

    # Look for specific elements with company data
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Check tables
    tables = soup.select("table")
    print(f"\nTables found: {len(tables)}")
    for i, t in enumerate(tables[:5]):
        rows = t.select("tr")
        print(f"  Table {i}: {len(rows)} rows")
        for r in rows[:10]:
            cells = [c.get_text(" ", strip=True)[:80] for c in r.select("td,th")]
            if cells:
                print(f"    {' | '.join(cells)}")

    # Check for specific CSS classes
    for cls in ["company-info", "tax-info", "detail", "info", "content"]:
        elems = soup.select(f"[class*='{cls}']")
        if elems:
            print(f"\n  Elements with class *{cls}*: {len(elems)}")
            for e in elems[:3]:
                txt = e.get_text(" ", strip=True)[:200]
                print(f"    tag={e.name} class={e.get('class')} text={txt}")

    # Check for dl/dt/dd (definition lists)
    dts = soup.select("dt")
    if dts:
        print(f"\nDefinition list <dt> items: {len(dts)}")
        for dt in dts[:10]:
            dd = dt.find_next_sibling("dd")
            dt_text = dt.get_text(" ", strip=True)[:60]
            dd_text = dd.get_text(" ", strip=True)[:100] if dd else "N/A"
            print(f"  {dt_text}: {dd_text}")

    # Check h1
    h1 = soup.select_one("h1")
    if h1:
        print(f"\nH1: {h1.get_text(' ', strip=True)[:100]}")

    # Dump text near "Mã số thuế", "vốn", "ngành"
    text = soup.get_text("\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for kw in ["Mã số thuế", "mã số thuế", "Vốn", "vốn", "Ngành nghề chính", "ngành nghề"]:
        for i, line in enumerate(lines):
            if kw.lower() in line.lower() and len(line) < 200:
                ctx = lines[max(0,i-1):i+4]
                print(f"\n  Near '{kw}':")
                for c in ctx:
                    print(f"    {c[:150]}")
                break

    # =============================================
    # thuvienphapluat.vn — Inspect search results
    # =============================================
    print("\n\n=== thuvienphapluat.vn SEARCH RESULTS ===")
    url = f"https://thuvienphapluat.vn/ma-so-thue?keyword={MST}"
    driver.get(url)
    WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(4)
    print(f"URL: {driver.current_url}")

    body = driver.page_source
    soup2 = BeautifulSoup(body, "html.parser")

    # Dump all links that might lead to detail
    links = soup2.select("a[href]")
    print(f"\nTotal links: {len(links)}")
    for a in links:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)[:80]
        if MST in href or MST in text or "ma-so-thue" in href.lower():
            print(f"  {href[:120]} -> {text}")

    # Check if there are result items
    for cls in ["result", "item", "company", "search"]:
        elems = soup2.select(f"[class*='{cls}']")
        if elems:
            print(f"\nElems with class *{cls}*: {len(elems)}")
            for e in elems[:3]:
                txt = e.get_text(" ", strip=True)[:120]
                print(f"  tag={e.name} class={e.get('class')} text={txt}")

    # Also check thuvienphapluat.vn input name
    for inp in driver.find_elements(By.TAG_NAME, "input"):
        try:
            n = inp.get_attribute("name") or ""
            v = inp.is_displayed()
            if v and n:
                val = inp.get_attribute("value") or ""
                print(f"\n  visible input: name={n!r} value={val[:30]!r}")
        except:
            pass

finally:
    driver.quit()
print("\nDONE")
