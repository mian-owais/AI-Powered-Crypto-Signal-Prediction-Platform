# Vercel Full Stack Deployment Guide

You have successfully configured the project to deploy **BOTH** the frontend and backend to Vercel!

## 🏗️ Architecture Changes

Since Vercel Serverless cannot host the original Streamlit app (which requires a persistent server), we have created a **Vercel-compatible Web Frontend**.

- **Backend:** `api/app.py` (Python/Flask) - Handles logic and ML predictions.
- **Frontend:** `public/index.html` (HTML/JS) - A lightweight, fast UI that talks to the backend.

## 🚀 How to Deploy

### Option 1: Automatic Deployment (Git)

1.  **Push your changes** to GitHub:

    ```bash
    git add .
    git commit -m "Added Vercel frontend"
    git push origin master
    ```

2.  **Go to Vercel Dashboard:**

    - Import your repository.
    - Vercel will automatically detect the `vercel.json` configuration.
    - **Environment Variables:** Add `COINGECKO_API_KEY` if you have one (optional but recommended).

3.  **Deploy!**
    - Your app will be live at `https://your-project.vercel.app`.
    - The UI will load at the root URL.
    - The API will be at `/api/predict`.

### Option 2: Manual Deployment (CLI)

1.  Install Vercel CLI: `npm i -g vercel`
2.  Run: `vercel`
3.  Follow the prompts (keep defaults).

## 📝 Notes

- The original Streamlit app (`src/app/streamlit_app.py`) is still in the project but is **not used** for the Vercel deployment. You can still run it locally with `streamlit run src/app/streamlit_app.py`.
- This new frontend is lighter, faster, and 100% free on Vercel.
