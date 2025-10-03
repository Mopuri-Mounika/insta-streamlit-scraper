# app.py
import os
import traceback
from typing import List, Dict

import pandas as pd
import streamlit as st

# NOTE: we DO NOT import InstagramScraperSelenium at the top.
# We lazy-import it inside the button handler to avoid any circular import issues.

from core.cleaners import clean_dataframe_basic
from core.exporters import df_to_csv_bytes, df_to_xlsx_bytes


# -----------------------------
# Streamlit page configuration
# -----------------------------
st.set_page_config(page_title="Instagram Profile Scraper (Selenium)", layout="wide")
st.title("Instagram Profile Scraper (Selenium + Headless Chromium)")

with st.expander("How it works", expanded=False):
    st.markdown(
        """
- Enter an Instagram **username** (e.g., `@username`) or **profile URL** (e.g., `https://instagram.com/username/`).
- The app uses **Selenium + headless Chromium** to scroll the profile grid and collect `/p/` (posts) and `/reel/` (reels) URLs.
- Results can be downloaded as **CSV** or **Excel**.
- Set environment variables **`INSTAGRAM_USERNAME`** and **`INSTAGRAM_PASSWORD`** on the host (Render → Settings → Environment), then **Restart**.
        """
    )

# -----------------------------
# UI inputs
# -----------------------------
raw_input: str = st.text_input(
    "Instagram username or profile URL",
    placeholder="@user or https://instagram.com/user"
)
run = st.button("Scrape Post URLs")

# Simple env presence hint (doesn't show secrets)
env_user_present = bool(os.getenv("INSTAGRAM_USERNAME"))
env_pass_present = bool(os.getenv("INSTAGRAM_PASSWORD"))
st.caption(f"Env check → INSTAGRAM_USERNAME: **{env_user_present}**, INSTAGRAM_PASSWORD: **{env_pass_present}**")

# -----------------------------
# Run scraper
# -----------------------------
if run:
    if not raw_input or not raw_input.strip():
        st.error("Please enter a username or profile URL.")
        st.stop()

    with st.spinner("Scraping… this can take a moment on a cold start."):
        print(f"[APP] Start scrape for: {raw_input}", flush=True)
        print(f"[APP] ENV present? USER={env_user_present} PASS={env_pass_present}", flush=True)

        try:
            # LAZY IMPORT here to avoid circular imports
            from scrapers.instagram_selenium import InstagramScraperSelenium  # noqa: E402

            scraper = InstagramScraperSelenium()
            rows: List[Dict] = scraper.scrape_profile(raw_input)
            print(f"[APP] Scrape returned {len(rows) if rows else 0} rows", flush=True)

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
        except Exception as e:
            st.error(f"Error during scrape: {e}")
            tb = traceback.format_exc()
            print("[APP] Exception during scrape:\n" + tb, flush=True)

# -----------------------------
# Footer / tips
# -----------------------------
st.markdown(
    """
---
**Tips**
- If you see “No data returned”, confirm env vars are set on the host and **Restart** the service.
- Test with a known public profile first: `https://www.instagram.com/instagram/`.
- Free hosting may cold-start; first run can be slower.
"""
)
