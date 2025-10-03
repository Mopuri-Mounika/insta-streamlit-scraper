from typing import List, Dict, Optional
import os
import re
import time
import random
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def _normalize_instagram_input(raw: str) -> Optional[str]:
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
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def _login(driver: webdriver.Chrome, username: str, password: str) -> None:
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(random.uniform(4, 6))
    wait = WebDriverWait(driver, 20)
    u = wait.until(EC.presence_of_element_located((By.NAME, "username")))
    p = wait.until(EC.presence_of_element_located((By.NAME, "password")))
    u.send_keys(username)
    p.send_keys(password)
    submit = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]')))
    submit.click()
    time.sleep(random.uniform(5, 7))
    # dismiss popups
    for _ in range(3):
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"Not Now") or contains(text(),"Not now")]'))
            )
            btn.click()
            time.sleep(random.uniform(2, 4))
        except TimeoutException:
            break

def _collect_post_urls(driver: webdriver.Chrome, handle: str, max_idle_scrolls: int = 5) -> List[str]:
    profile_url = f"https://www.instagram.com/{handle}/"
    driver.get(profile_url)
    time.sleep(random.uniform(4, 6))
    post_urls = set()
    prev_count = 0
    idle = 0
    def pause():
        time.sleep(random.uniform(2.0, 4.0))
    while True:
        anchors = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"], a[href*="/reel/"]')
        for a in anchors:
            href = a.get_attribute("href")
            if href and ("/p/" in href or "/reel/" in href):
                post_urls.add(href.split("?")[0])
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        pause()
        curr = len(post_urls)
        if curr == prev_count:
            idle += 1
        else:
            idle = 0
        prev_count = curr
        if idle >= max_idle_scrolls:
            break
    return sorted(post_urls)

def _url_to_row(url: str) -> Dict:
    kind = "post" if "/p/" in url else ("reel" if "/reel/" in url else "unknown")
    m = re.search(r"/(p|reel)/([^/]+)/?", url)
    shortcode = m.group(2) if m else None
    return {"type": kind, "shortcode": shortcode, "post_url": url}

class InstagramScraperSelenium:
    def scrape_profile(self, handle_or_url: str) -> List[Dict]:
        handle = _normalize_instagram_input(handle_or_url)
        if not handle:
            return []
        user = os.getenv("INSTAGRAM_USERNAME", "")
        pwd = os.getenv("INSTAGRAM_PASSWORD", "")
        driver = _build_driver(headless=True)
        try:
            if user and pwd:
                _login(driver, user, pwd)
            urls = _collect_post_urls(driver, handle, max_idle_scrolls=5)
            return [_url_to_row(u) for u in urls]
        finally:
            driver.quit()