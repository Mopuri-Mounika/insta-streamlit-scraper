import streamlit as st
import pandas as pd
from scrapers.instagram_selenium import InstagramScraperSelenium
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

if run:
    if not raw_input or not raw_input.strip():
        st.error("Please enter a username or profile URL.")
        st.stop()

    with st.spinner("Scraping…"):
        rows = InstagramScraperSelenium().scrape_profile(raw_input)

    if not rows:
        st.warning("No data returned. Check the input or try again.")
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

    st.success("Done!")