# app.py
import os
import io
import re
import time
import random
from typing import List, Dict, Optional
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service

# --- Small helpers ------------------------------------------------------------
def normalize_input(raw: str) -> Optional[str]:
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

def build_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    # stable flags for low-RAM/headless
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--window-size=1280,1696")
    opts.add_argument("--disable-features=VizDisplayCompositor")
    opts.add_argument("--lang=en-US")
    opts.set_capability("pageLoadStrategy", "eager")
    # user agent + anti-automation
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    )
    # Let Selenium 4+ manage the driver locally (no path needed)
    # If you are on a server with chromium paths, set CHROME_BIN/CHROMEDRIVER envs.
    chrome_bin = os.getenv("CHROME_BIN")
    chromedriver = os.getenv("CHROMEDRIVER")
    if chrome_bin:
        opts.binary_location = chrome_bin
    service = Service(chromedriver) if chromedriver else None

    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass
    return driver

def dismiss_cookie_banner(driver: webdriver.Chrome):
    candidates = [
        '//button//*[contains(text(),"Allow all cookies")]/ancestor::button',
        '//button[contains(text(),"Allow all cookies")]',
        '//button//*[contains(text(),"Only allow essential cookies")]/ancestor::button',
        '//div[@role="dialog"]//button[contains(text(),"Accept")]',
        '//button[contains(text(),"Allow All")]',
    ]
    for xp in candidates:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp)))
            btn.click()
            time.sleep(1.0)
            break
        except Exception:
            pass

def login(driver: webdriver.Chrome, username: str, password: str):
    st.write("🔐 Logging in…")
    try:
        driver.get("https://www.instagram.com/accounts/login/")
    except WebDriverException:
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
        wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))).click()
    except TimeoutException:
        st.warning("Login form wasn’t found in time.")
        return
    time.sleep(random.uniform(6, 9))

    # dismiss post-login popups
    for _ in range(3):
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"Not Now") or contains(text(),"Not now")]'))
            ).click()
            time.sleep(1.0)
        except TimeoutException:
            break
    st.write("✅ Logged in.")

def collect_post_urls(driver: webdriver.Chrome, handle: str, max_idle_scrolls: int = 12) -> List[str]:
    """Use JS to grab all /p/ and /reel/ links while scrolling."""
    profile = f"https://www.instagram.com/{handle}/?hl=en"
    st.write(f"🌐 Visiting: {profile}")
    try:
        driver.get(profile)
    except WebDriverException:
        time.sleep(2)
        driver.get(profile)

    time.sleep(random.uniform(3, 5))
    dismiss_cookie_banner(driver)

    # login wall?
    try:
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.NAME, "username")))
        return ["__LOGIN_REQUIRED__"]
    except Exception:
        pass

    # quick checks
    if driver.find_elements(By.XPATH, '//*[contains(text(),"This account is private")]'):
        return []
    if driver.find_elements(By.XPATH, '//*[contains(text(),"No posts yet")]'):
        return []

    js_capture = """
    const hrefs = Array.from(document.querySelectorAll('a'))
      .map(a => a.href)
      .filter(h => h && (h.includes('/p/') || h.includes('/reel/')))
      .map(h => h.split('?')[0]);
    return Array.from(new Set(hrefs));
    """

    urls = set()
    prev, idle = 0, 0

    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a")))
    except TimeoutException:
        pass

    while True:
        try:
            found = driver.execute_script(js_capture) or []
        except WebDriverException:
            found = []
        for h in found:
            if "/p/" in h or "/reel/" in h:
                urls.add(h)

        st.write(f"📸 Collected so far: {len(urls)}")
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.85);")
        time.sleep(random.uniform(1.8, 3.4))

        curr = len(urls)
        idle = idle + 1 if curr == prev else 0
        prev = curr
        if idle >= max_idle_scrolls:
            break

    return sorted(urls)

def url_to_row(url: str) -> Dict:
    kind = "post" if "/p/" in url else ("reel" if "/reel/" in url else "unknown")
    m = re.search(r"/(p|reel)/([^/]+)/?", url)
    shortcode = m.group(2) if m else None
    return {"type": kind, "shortcode": shortcode, "post_url": url}

# --- Streamlit UI -------------------------------------------------------------
st.set_page_config(page_title="Instagram Scraper", layout="wide")
st.title("Instagram Profile Scraper (Selenium)")

with st.expander("How it works", expanded=False):
    st.markdown(
        "- Enter an Instagram **username** (e.g. `@user`) or **profile URL**.\n"
        "- App will **log in** if you supply `INSTAGRAM_USERNAME` & `INSTAGRAM_PASSWORD` env vars.\n"
        "- It scrolls the profile and extracts `/p/` and `/reel/` URLs.\n"
        "- Download results as **CSV** or **Excel**."
    )

raw = st.text_input("Instagram username or profile URL", placeholder="@user or https://instagram.com/user", key="profile_input")
run = st.button("Scrape Post URLs", key="run_btn")

st.caption(
    f"Env → INSTAGRAM_USERNAME: **{bool(os.getenv('INSTAGRAM_USERNAME'))}**, "
    f"INSTAGRAM_PASSWORD: **{bool(os.getenv('INSTAGRAM_PASSWORD'))}**"
)

if run:
    handle = normalize_input(raw)
    if not handle:
        st.error("Please enter a valid username or profile URL.")
        st.stop()

    user = os.getenv("INSTAGRAM_USERNAME", "")
    pwd = os.getenv("INSTAGRAM_PASSWORD", "")

    with st.spinner("Launching headless browser and scraping…"):
        driver = build_driver(headless=True)
        try:
            if user and pwd:
                login(driver, user, pwd)
            urls = collect_post_urls(driver, handle, max_idle_scrolls=12)

            if urls == ["__LOGIN_REQUIRED__"] and user and pwd:
                login(driver, user, pwd)
                urls = collect_post_urls(driver, handle, max_idle_scrolls=12)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    if not urls or urls == ["__LOGIN_REQUIRED__"]:
        st.warning("No data returned. The account may be private or the grid didn’t load. Try again.")
        st.stop()

        # Build DataFrame from the collected URLs
    df = pd.DataFrame([url_to_row(u) for u in urls])

    st.subheader(f"Collected {len(df)} URLs")
    st.dataframe(df, use_container_width=True)

    # ----------------- Downloads -----------------
    c1, c2 = st.columns(2)

    # CSV download
    with c1:
        st.download_button(
            "⬇️ Download CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="instagram_post_urls.csv",
            mime="text/csv",
            key="csv_dl",
        )

    # Excel download (in-memory; safe on Windows)
    import io
    excel_buffer = io.BytesIO()

    # Ensure at least one sheet is written
    df_to_write = df if not df.empty else pd.DataFrame({"post_url": []})

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df_to_write.to_excel(writer, index=False, sheet_name="posts")
    excel_buffer.seek(0)

    with c2:
        st.download_button(
            "⬇️ Download Excel",
            data=excel_buffer,
            file_name="instagram_post_urls.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="xlsx_dl",
        )

    st.success("Done!")
