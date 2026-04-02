"""Test JS form submit + direct URL on masothue.com and thuvienphapluat.vn"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time

MST = "0100107518"  # Vinamilk

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
    # TEST 1: masothue.com — JS form.submit()
    # =============================================
    print("=== masothue.com JS submit ===")
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
    result = driver.execute_script(js_submit, MST)
    print(f"  JS result: {result}")
    time.sleep(5)
    print(f"  URL after: {driver.current_url}")

    body = driver.page_source
    print(f"  Has MST: {MST in body}, len={len(body)}")

    soup = BeautifulSoup(body, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Check if we landed on search results or detail page
    for kw in ["Vốn điều lệ", "Ngành nghề", "Email", "Loại hình"]:
        for line in text.split("\n"):
            if kw.lower() in line.lower():
                print(f"  [{kw}] {line[:120]}")
                break

    # Find detail links
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if MST in href:
            print(f"  link: {href} -> {a.get_text()[:60]}")

    # =============================================
    # TEST 2: masothue.com — Direct URL with slug
    # =============================================
    print("\n=== masothue.com direct URL ===")
    # Try navigating to the URL found from search, or try common patterns
    direct_url = f"https://masothue.com/{MST}"
    driver.get(direct_url)
    time.sleep(3)
    print(f"  URL: {driver.current_url}")
    print(f"  Title: {driver.title}")
    body2 = driver.page_source
    print(f"  Has MST: {MST in body2}, len={len(body2)}")

    soup2 = BeautifulSoup(body2, "html.parser")
    text2 = soup2.get_text("\n", strip=True)
    for kw in ["Vốn điều lệ", "Ngành nghề", "Email"]:
        for line in text2.split("\n"):
            if kw.lower() in line.lower():
                print(f"  [{kw}] {line[:120]}")
                break

    # =============================================
    # TEST 3: thuvienphapluat.vn via URL params
    # =============================================
    print("\n=== thuvienphapluat.vn URL param ===")
    tvpl_url = f"https://thuvienphapluat.vn/ma-so-thue?keyword={MST}"
    driver.get(tvpl_url)
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(3)
    print(f"  URL: {driver.current_url}")
    print(f"  Title: {driver.title}")
    body3 = driver.page_source
    print(f"  Has MST: {MST in body3}, len={len(body3)}")

    import re
    pat = re.compile(rf"/ma-so-thue/[^\"\s>]*{MST}[^\"\s>]*\.html", re.I)
    for m in pat.findall(body3)[:5]:
        print(f"  detail link: {m}")

    soup3 = BeautifulSoup(body3, "html.parser")
    text3 = soup3.get_text("\n", strip=True)
    for kw in ["Vốn điều lệ", "Ngành nghề"]:
        for line in text3.split("\n"):
            if kw.lower() in line.lower():
                print(f"  [{kw}] {line[:120]}")
                break

    # =============================================
    # TEST 4: thuvienphapluat.vn JS form submit
    # =============================================
    print("\n=== thuvienphapluat.vn JS submit ===")
    driver.get("https://thuvienphapluat.vn/ma-so-thue")
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(2)

    # List inputs for debugging
    for inp in driver.find_elements(By.TAG_NAME, "input"):
        try:
            n = inp.get_attribute("name") or ""
            t = inp.get_attribute("type") or ""
            v = inp.is_displayed()
            if v:
                print(f"  visible input: name={n!r} type={t!r}")
        except:
            pass

    js_tvpl = (
        "var inp = document.querySelector('input[name=\"keyword\"]') "
        "|| document.querySelector('input[name=\"q\"]') "
        "|| document.querySelector('input[type=\"search\"]');"
        "if (!inp) return 'no_input';"
        "inp.value = arguments[0];"
        "var form = inp.closest('form');"
        "if (form) { form.submit(); return 'form_submitted'; }"
        "return 'no_form';"
    )
    result4 = driver.execute_script(js_tvpl, MST)
    print(f"  JS result: {result4}")
    time.sleep(5)
    print(f"  URL after: {driver.current_url}")
    body4 = driver.page_source
    print(f"  Has MST: {MST in body4}, len={len(body4)}")

finally:
    driver.quit()

print("\nDONE")
