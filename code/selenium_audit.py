import time
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from audit_config import BASE_URL, LOGIN_URL, MAX_PAGES, TAG_SELECTOR
from text_detector import clean_text, looks_not_vietnamized, should_ignore_candidate


def build_driver() -> webdriver.Chrome:
    """Create Selenium Chrome driver for UI audit."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    return webdriver.Chrome(options=options)


def safe_quit(driver: webdriver.Chrome) -> None:
    """Quit driver safely without failing the audit flow."""
    try:
        driver.quit()
    except Exception:
        return


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/") or BASE_URL.rstrip("/")


def is_internal_page(url: str) -> bool:
    """Check if URL is a crawlable page in the same site."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if "beta-noibo.kydai.vn" not in parsed.netloc:
        return False

    blocked_ext = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".css",
        ".js",
        ".ico",
        ".webp",
        ".pdf",
    )
    if parsed.path.lower().endswith(blocked_ext):
        return False

    return True


def discover_pages(driver: webdriver.Chrome, start_url: str, max_pages: int) -> list[str]:
    """Discover internal pages by collecting links from homepage."""
    driver.get(start_url)
    WebDriverWait(driver, 20).until(ec.presence_of_element_located((By.TAG_NAME, "body")))
    WebDriverWait(driver, 20).until(ec.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href]")))

    found: list[str] = [normalize_url(start_url)]
    seen: set[str] = {normalize_url(start_url)}

    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = clean_text(anchor.get_attribute("href") or "")
        if not href:
            continue

        abs_url = normalize_url(urljoin(start_url, href))
        if not is_internal_page(abs_url):
            continue
        if abs_url in seen:
            continue

        seen.add(abs_url)
        found.append(abs_url)
        if len(found) >= max_pages:
            break

    return found


def find_first_visible(driver: webdriver.Chrome, selectors: list[str]):
    """Find the first displayed element that matches any selector."""
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            if element.is_displayed() and element.is_enabled():
                return element
    return None


def login(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Try to login and return True when account appears signed-in."""
    try:
        driver.get(LOGIN_URL)
        WebDriverWait(driver, 20).until(ec.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.0)

        username_input = find_first_visible(
            driver,
            [
                "input[name='username']",
                "input[id*='user']",
                "input[autocomplete='username']",
                "input[type='text']",
            ],
        )
        password_input = find_first_visible(
            driver,
            [
                "input[name='password']",
                "input[id*='pass']",
                "input[autocomplete='current-password']",
                "input[type='password']",
            ],
        )

        if not username_input or not password_input:
            return False

        username_input.clear()
        username_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

        submit_button = find_first_visible(
            driver,
            [
                "button[type='submit']",
                "input[type='submit']",
                "button[name='login']",
                "button",
            ],
        )

        if submit_button:
            submit_button.click()
        else:
            password_input.submit()

        WebDriverWait(driver, 20).until(ec.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.5)

        page_text = clean_text(driver.page_source.lower())
        current_url = driver.current_url.lower()
        if "/login" in current_url:
            return False
        if "dang nhap" in page_text and username.lower() not in page_text:
            return False
        return True
    except TimeoutException:
        return False


def collect_texts_from_page(driver: webdriver.Chrome, page_url: str, scope: str) -> list[dict[str, str]]:
    """Extract visible text and UI labels from one page."""
    try:
        driver.get(page_url)
        WebDriverWait(driver, 20).until(ec.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.2)
    except TimeoutException:
        return [
            {
                "scope": scope,
                "page_url": page_url,
                "text": "[timeout]",
                "source": "system",
                "reason": "page_timeout",
            }
        ]
    except Exception as error:
        return [
            {
                "scope": scope,
                "page_url": page_url,
                "text": "[page_error]",
                "source": "system",
                "reason": f"page_error:{error.__class__.__name__}",
            }
        ]

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for el in driver.find_elements(By.CSS_SELECTOR, TAG_SELECTOR):
        if not el.is_displayed():
            continue

        candidates = [
            (clean_text(el.text), "visible_text"),
            (clean_text(el.get_attribute("placeholder") or ""), "placeholder"),
            (clean_text(el.get_attribute("title") or ""), "title"),
            (clean_text(el.get_attribute("aria-label") or ""), "aria_label"),
            (clean_text(el.get_attribute("alt") or ""), "alt"),
            (clean_text(el.get_attribute("value") or ""), "value"),
        ]

        for text_value, source in candidates:
            if not text_value:
                continue
            if should_ignore_candidate(text_value):
                continue

            key = (text_value, source)
            if key in seen:
                continue
            seen.add(key)

            suspicious, reason = looks_not_vietnamized(text_value)
            if suspicious:
                rows.append(
                    {
                        "scope": scope,
                        "page_url": page_url,
                        "text": text_value,
                        "source": source,
                        "reason": reason,
                    }
                )

    return rows


def run_scope_audit(scope: str, username: str | None = None, password: str | None = None) -> list[dict[str, str]]:
    """Run audit with dedicated driver per scope for better stability."""
    driver = build_driver()
    try:
        if username and password:
            success = login(driver, username, password)
            if not success:
                return [
                    {
                        "scope": scope,
                        "page_url": LOGIN_URL,
                        "text": "[login_failed]",
                        "source": "system",
                        "reason": "cannot_login",
                    }
                ]

        try:
            pages = discover_pages(driver, BASE_URL, MAX_PAGES)
        except Exception as error:
            return [
                {
                    "scope": scope,
                    "page_url": BASE_URL,
                    "text": "[discover_failed]",
                    "source": "system",
                    "reason": f"discover_error:{error.__class__.__name__}",
                }
            ]

        all_rows: list[dict[str, str]] = []
        for page in pages:
            all_rows.extend(collect_texts_from_page(driver, page, scope))

        return all_rows
    finally:
        safe_quit(driver)
