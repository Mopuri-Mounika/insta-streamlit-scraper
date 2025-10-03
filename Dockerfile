FROM python:3.11-slim

# Install Chromium + Chromedriver and deps
RUN apt-get update && apt-get install -y --no-install-recommends \ 
    chromium \ 
    chromium-driver \ 
    fonts-liberation \ 
    libglib2.0-0 \ 
    libnss3 \ 
    libgconf-2-4 \ 
    libasound2 \ 
    libpangocairo-1.0-0 \ 
    libatk1.0-0 \ 
    libcairo2 \ 
    libx11-xcb1 \ 
    libxcomposite1 \ 
    libxcursor1 \ 
    libxdamage1 \ 
    libxi6 \ 
    libxtst6 \ 
    libnss3 \ 
    libxrandr2 \ 
    libglib2.0-0 \ 
    libxkbcommon0 \ 
    libxshmfence1 \ 
    libgbm1 \ 
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER=/usr/bin/chromedriver
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8501
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]