# Streamlit + Selenium Instagram Scraper (Docker Deploy)

This is a Streamlit app that accepts an Instagram **username or profile URL**,
scrapes **all post/reel URLs** with **Selenium + headless Chromium**, then lets you
**download CSV/XLSX**.

## Why Docker?
Streamlit Community Cloud does **not** provide Chrome/Chromedriver. Use Docker on
Render / Fly.io / Railway / your VPS. This repo includes a `Dockerfile` that installs
Chromium + Chromedriver for headless scraping.

## Run locally
```bash
pip install -r requirements.txt
# Set environment variables (or create a .env file)
export INSTAGRAM_USERNAME="your_login"
export INSTAGRAM_PASSWORD="your_password"
streamlit run app.py
```

## Docker build & run
```bash
docker build -t ig-scraper .
docker run -p 8501:8501       -e INSTAGRAM_USERNAME="your_login"       -e INSTAGRAM_PASSWORD="your_password"       ig-scraper
```

## Deploy on Render (example)
1. Push to GitHub.
2. On Render: New → Web Service → Build from repo.
3. Select **Docker** runtime (it will use `Dockerfile`).
4. Add env vars: `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`.
5. Deploy.