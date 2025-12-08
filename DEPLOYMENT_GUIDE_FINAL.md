# AI Crypto Signal Prediction - Deployment Guide

This guide covers how to deploy the **API** to Vercel and the **Streamlit UI** to Render.

## 🚀 Quick Start: Push to GitHub

Your code is already configured. Push your latest changes:

```bash
git add .
git commit -m "Ready for deployment"
git push origin master
```

---

## 🌐 Part 1: Deploy API to Vercel

The API backend (`api/app.py`) is optimized for Vercel's serverless environment.

1.  **Login to Vercel:**
    Go to [vercel.com](https://vercel.com) and sign up/login.

2.  **Import Project:**
    *   Click **"Add New..."** -> **"Project"**.
    *   Select **"Import"** next to your GitHub repository: `AI-Powered-Crypto-Signal-Prediction-Platform`.

3.  **Configure:**
    *   **Framework Preset:** Select `Other`.
    *   **Root Directory:** Keep as `./`.
    *   **Build Command:** `pip install -r requirements-vercel.txt`
    *   **Output Directory:** Keep default (usually `.` or `public`).
    *   **Environment Variables:** Add any API keys if you have them (e.g., `COINGECKO_API_KEY`).

4.  **Deploy:**
    *   Click **"Deploy"**.
    *   Once finished, your API will be available at `https://your-project-name.vercel.app`.

    **Test the API:**
    *   `https://your-project-name.vercel.app/api/status`
    *   `https://your-project-name.vercel.app/api/predict?crypto=bitcoin`

---

## 🖥️ Part 2: Deploy Streamlit UI to Render (Recommended)

The Streamlit User Interface (`src/app/streamlit_app.py`) requires a persistent server, which Vercel Serverless doesn't support well. **Render** is the best free/cheap option.

1.  **Login to Render:**
    Go to [render.com](https://render.com) and sign up/login.

2.  **Create Web Service:**
    *   Click **"New +"** -> **"Web Service"**.
    *   Connect your GitHub repository.

3.  **Configure:**
    *   **Name:** `crypto-bot-ui`
    *   **Runtime:** `Python 3`
    *   **Build Command:** `pip install -r requirements.txt`
    *   **Start Command:** `streamlit run src/app/streamlit_app.py`

4.  **Deploy:**
    *   Click **"Create Web Service"**.
    *   Render will build and start your app. This may take a few minutes.

---

## ⚠️ Important Notes

*   **Vercel Limits:** Vercel functions have a 10s (free) or 60s (pro) timeout. Complex model training might time out. The API is designed to use cached models to avoid this.
*   **Data Persistence:** Vercel is stateless. Models trained in one request might not be available in the next if the instance recycles. The current setup uses in-memory caching which is temporary. For production, you'd want to save models to S3 or a database.
