# app.py
import os
import traceback
from typing import List, Dict

import pandas as pd
import streamlit as st

# NOTE: do NOT import InstagramScraperSelenium at the top.
from core.cleaners import clean_dataframe_basic
from core.exporters import df_to_csv_bytes, df_to_xlsx_bytes

st.set_page_config(page_title="Instagram Profile Scraper (Selenium)", layout="wide")
st.title("Instagram Profile Scraper (Selenium + Headless Chromium)")

with st.expander("How it works", expanded=False):
    st.write("""
    - Enter an Instagram **username** (e.g., `@example`) or **profile URL**.
    - The app uses **Selenium + headless Chromium** to scroll the profile and collect `/p/` and `/reel/` URLs.
    - Download results as **CSV/XLSX**.
    - Set env vars `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` for login if needed.
    """)

raw_input = st.text_input("Instagram username or profile URL", placeholder="@user or https://instagram.com/user")
run = st.button("Scrape Post URLs")

# simple env presence hint (doesn't reveal secrets)
st.caption(f"Env check → INSTAGRAM_USERNAME: **{bool(os.getenv('INSTAGRAM_USERNAME'))}**, "
           f"INSTAGRAM_PASSWORD: **{bool(os.getenv('INSTAGRAM_PASSWORD'))}**")

if run:
    if not raw_input or not raw_input.strip():
        st.error("Please enter a username or profile URL.")
        st.stop()

    with st.spinner("Scraping…"):
        try:
            # Lazy import here to avoid circular import issues
            from scrapers.instagram_selenium import InstagramScraperSelenium  # noqa: E402

            scraper = InstagramScraperSelenium()
            rows: List[Dict] = scraper.scrape_profile(raw_input)
        except Exception as e:
            st.error(f"Error during scrape: {e}")
            print("[APP] Exception:", e, flush=True)
            print(traceback.format_exc(), flush=True)
            st.stop()

    if not rows:
        st.warning("No data returned. Try a public profile first (e.g., https://www.instagram.com/instagram/).")
        st.stop()

    df = pd.DataFrame(rows)
    df = clean_dataframe_basic(df)

    st.subheader("Preview")
    st.dataframe(df.head(200), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Download CSV",
            data=df_to_csv_bytes(df),
            file_name="instagram_post_urls.csv",
            mime="text/csv"
        )
    with c2:
        st.download_button(
            "⬇️ Download Excel",
            data=df_to_xlsx_bytes(df),
            file_name="instagram_post_urls.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.success(f"Done! Collected {len(df)} URLs.")
