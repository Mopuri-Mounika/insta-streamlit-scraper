# scrapers/instagram_selenium.py
from typing import List, Dict, Optional
import os
import re
import time
import random
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


# ----------------------------
# Utilities
# ----------------------------

def _normalize_instagram_input(raw: str) -> Optional[str]:
    """Accepts @user / user / https://instagram.com/user and returns 'user'."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("@"):
        text = text[1:]
    if text.startswith("http://") or text.startswith("https://"):
        try:
            p = urlparse(text)
            seg = (p.path or "").strip("/").split("/")[0]
            if seg:
                text = seg
        except Exception:
            pass
    return text if re.match(r"^[A-Za-z0-9._]{1,100}$", text) else None


def _build_driver(headless: bool = True) -> webdriver.Chrome:
    """Build a Chrome driver that works reliably on small containers (Render free tier)."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")

    # Stability flags for low-RAM headless envs
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--hide-scrollbars")
    chrome_options.add_argument("--window-size=1280,1696")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")

    # Load quicker / avoid long hangs
    chrome_options.set_capability("pageLoadStrategy", "eager")

    # Anti-automation bits
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit(537.36) (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    )

    # Explicit paths for Render’s apt packages
    chrome_options.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")
    service = Service(os.getenv("CHROMEDRIVER", "/usr/bin/chromedriver"))

    driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass
    return driver


def _dismiss_cookie_banner(driver: webdriver.Chrome):
    """Try to accept/close cookie banners that block the grid."""
    candidates = [
        '//button//*[contains(text(),"Allow all cookies")]/ancestor::button',
        '//button//*[contains(text(),"Allow All")]/ancestor::button',
        '//button//*[contains(text(),"Only allow essential cookies")]/ancestor::button',
        '//button[contains(text(),"Allow all cookies")]',
        '//button[contains(text(),"Allow All")]',
        '//button[contains(text(),"Only allow essential cookies")]',
        '//div[@role="dialog"]//button[contains(text(),"Accept")]',
    ]
    for xp in candidates:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp)))
            btn.click()
            time.sleep(1.2)
            print("[SCRAPER] Cookie banner dismissed", flush=True)
            break
        except Exception:
            pass


def _login(driver: webdriver.Chrome, username: str, password: str) -> None:
    """Log in to Instagram (for public reliability and private profiles)."""
    print("[SCRAPER] Logging in…", flush=True)
    try:
        driver.get("https://www.instagram.com/accounts/login/")
    except WebDriverException as e:
        print(f"[SCRAPER] driver.get(login) crashed: {e}", flush=True)
        time.sleep(2)
        driver.get("https://www.instagram.com/accounts/login/")

    time.sleep(random.uniform(3.5, 5.5))
    wait = WebDriverWait(driver, 30)

    try:
        u = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        p = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        u.clear(); p.clear()
        u.send_keys(username)
        p.send_keys(password)
        submit = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]')))
        submit.click()
    except TimeoutException:
        print("[SCRAPER] Login form not found in time", flush=True)
        return

    # Give it time to authenticate and land
    time.sleep(random.uniform(6, 9))

    # Dismiss potential popups
    for _ in range(3):
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//button[contains(text(),"Not Now") or contains(text(),"Not now")]')
                )
            )
            btn.click()
            time.sleep(1.2)
        except TimeoutException:
            break

    print("[SCRAPER] Login step complete", flush=True)


def _collect_post_urls(driver: webdriver.Chrome, handle: str, max_idle_scrolls: int = 10) -> List[str]:
    """Scroll the profile grid, collecting /p/ (posts) and /reel/ (reels)."""
    profile_url = f"https://www.instagram.com/{handle}/"
    print(f"[SCRAPER] Visiting: {profile_url}", flush=True)

    try:
        driver.get(profile_url)
    except WebDriverException as e:
        print(f"[SCRAPER] driver.get(profile) crashed: {e}", flush=True)
        time.sleep(2)
        driver.get(profile_url)

    time.sleep(random.uniform(3, 5))
    _dismiss_cookie_banner(driver)

    # If a login wall appears, signal to caller
    try:
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.NAME, "username")))
        print("[SCRAPER] Login wall detected on profile page", flush=True)
        return ["__LOGIN_REQUIRED__"]
    except Exception:
        pass

    # Private / no-posts checks
    if driver.find_elements(By.XPATH, '//*[contains(text(),"This account is private")]'):
        print("[SCRAPER] Private account", flush=True); return []
    if driver.find_elements(By.XPATH, '//*[contains(text(),"No posts yet")]'):
        print("[SCRAPER] No posts yet", flush=True); return []

    # Wait for anchors to appear
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/p/"], a[href*="/reel/"]'))
        )
    except TimeoutException:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

    post_urls = set()
    prev_count, idle = 0, 0

    def capture() -> int:
        anchors = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"], a[href*="/reel/"]')
        for a in anchors:
            href = a.get_attribute("href")
            if href and ("/p/" in href or "/reel/" in href):
                post_urls.add(href.split("?")[0])
        return len(anchors)

    n0 = capture()
    print(f"[SCRAPER] Initial anchors found: {n0}", flush=True)

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2.0, 3.6))
        capture()
        curr = len(post_urls)
        print(f"[SCRAPER] Collected so far: {curr}", flush=True)
        idle = idle + 1 if curr == prev_count else 0
        prev_count = curr
        if idle >= max_idle_scrolls:
            break

    print(f"[SCRAPER] Final posts: {len(post_urls)}", flush=True)
    return sorted(post_urls)


def _url_to_row(url: str) -> Dict:
    kind = "post" if "/p/" in url else ("reel" if "/reel/" in url else "unknown")
    m = re.search(r"/(p|reel)/([^/]+)/?", url)
    shortcode = m.group(2) if m else None
    return {"type": kind, "shortcode": shortcode, "post_url": url}


# ----------------------------
# Public entry
# ----------------------------

class InstagramScraperSelenium:
    def scrape_profile(self, handle_or_url: str) -> List[Dict]:
        handle = _normalize_instagram_input(handle_or_url)
        if not handle:
            print("[SCRAPER] Invalid handle", flush=True)
            return []

        user = os.getenv("INSTAGRAM_USERNAME", "")
        pwd = os.getenv("INSTAGRAM_PASSWORD", "")

        driver = _build_driver(headless=True)
        try:
            # 🔐 Login first if credentials are available (most reliable on Render)
            if user and pwd:
                _login(driver, user, pwd)
            else:
                print("[SCRAPER] No credentials set; attempting public scrape", flush=True)

            urls = _collect_post_urls(driver, handle, max_idle_scrolls=10)

            # If a login wall somehow appeared, retry once after login
            if urls == ["__LOGIN_REQUIRED__"] and user and pwd:
                _login(driver, user, pwd)
                urls = _collect_post_urls(driver, handle, max_idle_scrolls=10)

            if not urls or urls == ["__LOGIN_REQUIRED__"]:
                print("[SCRAPER] No URLs collected", flush=True)
                return []

            return [_url_to_row(u) for u in urls]
        finally:
            driver.quit()
