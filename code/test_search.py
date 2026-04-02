"""Quick test: verify Selenium can search MST on masothue.com and thuvienphapluat.vn"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time, re

TEST_MST = "0317985837"

def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--log-level=3")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    return webdriver.Chrome(options=opts)

def test_masothue(driver):
    print("=== TEST masothue.com ===")
    driver.get("https://masothue.com/")
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(3)
    print(f"Title: {driver.title}")
    print(f"URL: {driver.current_url}")

    for inp in driver.find_elements(By.TAG_NAME, "input"):
        try:
            n = inp.get_attribute("name") or ""
            t = inp.get_attribute("type") or ""
            p = inp.get_attribute("placeholder") or ""
            v = inp.is_displayed()
            print(f"  input: name={n!r} type={t!r} ph={p[:40]!r} vis={v}")
        except:
            pass

    search = None
    for sel in ["input[name='q']", "input[type='search']", "input.form-control", "input[type='text']"]:
        for e in driver.find_elements(By.CSS_SELECTOR, sel):
            if e.is_displayed():
                search = e
                print(f"  >> FOUND via {sel!r}")
                break
        if search:
            break

    if not search:
        print("  !! NO SEARCH INPUT")
        return

    # Try JS input + form submit (bypasses overlay issues)
    try:
        driver.execute_script("arguments[0].value = arguments[1];", search, TEST_MST)
        form = search.find_element(By.XPATH, "./ancestor::form")
        driver.execute_script("arguments[0].submit();", form)
        print("  >> Submitted via JS form.submit()")
    except Exception as e:
        print(f"  JS submit failed: {e}")
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(search).click().send_keys(TEST_MST).send_keys(Keys.ENTER).perform()
            print("  >> Submitted via ActionChains")
        except Exception as e2:
            print(f"  ActionChains also failed: {e2}")
            return

    time.sleep(5)
    print(f"After search URL: {driver.current_url}")
    body = driver.page_source
    print(f"Body has MST: {TEST_MST in body}, len={len(body)}")

    soup = BeautifulSoup(body, "html.parser")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if TEST_MST in href:
            print(f"  detail: {href} => {a.get_text()[:60]}")

def test_masothue_direct_url(driver):
    """Fallback: try direct URL pattern instead of search form."""
    print("\n=== TEST masothue.com DIRECT URL ===")
    url = f"https://masothue.com/{TEST_MST}"
    driver.get(url)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(3)
    print(f"URL: {driver.current_url}")
    print(f"Title: {driver.title}")
    body = driver.page_source
    print(f"Body has MST: {TEST_MST in body}, len={len(body)}")
    
    # Check for key fields
    soup = BeautifulSoup(body, "html.parser")
    text = soup.get_text("\n", strip=True)
    for kw in ["Vốn điều lệ", "Von dieu le", "Ngành nghề", "Nganh nghe", "Email"]:
        if kw.lower() in text.lower():
            # Find the line
            for line in text.split("\n"):
                if kw.lower() in line.lower():
                    print(f"  FOUND: {line[:100]}")
                    break

def test_tvpl(driver):
    print("\n=== TEST thuvienphapluat.vn ===")
    driver.get("https://thuvienphapluat.vn/ma-so-thue")
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(3)
    print(f"Title: {driver.title}")
    print(f"URL: {driver.current_url}")

    for inp in driver.find_elements(By.TAG_NAME, "input"):
        try:
            n = inp.get_attribute("name") or ""
            t = inp.get_attribute("type") or ""
            p = inp.get_attribute("placeholder") or ""
            v = inp.is_displayed()
            print(f"  input: name={n!r} type={t!r} ph={p[:40]!r} vis={v}")
        except:
            pass

    search = None
    for sel in ["input[name='keyword']", "input[name='q']", "input[type='search']", "input[type='text']"]:
        for e in driver.find_elements(By.CSS_SELECTOR, sel):
            if e.is_displayed():
                search = e
                print(f"  >> FOUND via {sel!r}")
                break
        if search:
            break

    if not search:
        print("  !! NO SEARCH INPUT")
        return

    try:
        driver.execute_script("arguments[0].value = arguments[1];", search, TEST_MST)
        form = search.find_element(By.XPATH, "./ancestor::form")
        driver.execute_script("arguments[0].submit();", form)
        print("  >> Submitted via JS form.submit()")
    except Exception as e:
        print(f"  JS submit failed: {e}")
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(search).click().send_keys(TEST_MST).send_keys(Keys.ENTER).perform()
            print("  >> Submitted via ActionChains")
        except Exception as e2:
            print(f"  ActionChains also failed: {e2}")
            return
    time.sleep(5)
    print(f"After search URL: {driver.current_url}")
    body = driver.page_source
    print(f"Body has MST: {TEST_MST in body}, len={len(body)}")

    pat = re.compile(rf"/ma-so-thue/[^\"\s>]*-mst-{TEST_MST}\.html", re.I)
    for m in pat.findall(body)[:5]:
        print(f"  detail: {m}")
    
    # Also check for key field labels
    soup = BeautifulSoup(body, "html.parser")
    text = soup.get_text("\n", strip=True)
    for kw in ["V\u1ed1n \u0111i\u1ec1u l\u1ec7", "Ng\u00e0nh ngh\u1ec1"]:
        if kw.lower() in text.lower():
            for line in text.split("\n"):
                if kw.lower() in line.lower():
                    print(f"  FOUND: {line[:100]}")
                    break

if __name__ == "__main__":
    driver = make_driver()
    try:
        test_masothue(driver)
        test_masothue_direct_url(driver)
        test_tvpl(driver)
    finally:
        driver.quit()
    print("\nDONE")
