# Vercel Deployment Guide

## Prerequisites
- GitHub account (code already pushed)
- Vercel account (free at https://vercel.com)
- Git installed

## Step-by-Step Deployment

### Option 1: Deploy via Vercel CLI (Recommended)

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel:**
   ```bash
   vercel login
   ```

3. **Navigate to project directory:**
   ```bash
   cd "/c/Users/DELL/Downloads/Cryptocurrency-Prediction-AI-Bot-main (4)/Cryptocurrency-Prediction-AI-Bot-main"
   ```

4. **Deploy the project:**
   ```bash
   vercel
   ```

5. **Follow the prompts:**
   - Confirm project setup
   - Set project name (e.g., `crypto-prediction-bot`)
   - Select framework: `Other`
   - Root directory: `.`

### Option 2: Deploy via GitHub Integration (Easiest)

1. **Go to Vercel Dashboard:** https://vercel.com/dashboard

2. **Click "Add New Project"**

3. **Import from Git:**
   - Click "Import Project"
   - Select "Import Git Repository"
   - Paste your repository URL:
     ```
     https://github.com/mian-owais/AI-Powered-Crypto-Signal-Prediction-Platform
     ```

4. **Configure Project:**
   - **Project Name:** `crypto-prediction-bot`
   - **Framework Preset:** `Other`
   - **Build Command:** `pip install -r requirements-vercel.txt`
   - **Install Command:** `pip install -r requirements-vercel.txt`
   - **Output Directory:** `.`

5. **Environment Variables (Optional):**
   - Add any sensitive API keys or configuration
   - Click "Add Environment Variable"

6. **Deploy:**
   - Click "Deploy"
   - Wait for build to complete (5-10 minutes)

## Important Notes

### Limitations on Vercel
- Vercel's serverless functions have **execution time limits** (10-60 seconds)
- **Large ML models** may exceed memory limits (3GB)
- **Real-time data fetching** may timeout
- **File persistence** is limited (no persistent storage between requests)

### Better Alternatives for ML Projects

**Recommended Platforms:**
1. **Render** (Python-friendly, better for background jobs)
   - URL: https://render.com
   - Deploy: Connect GitHub, select Python environment

2. **Railway** (Great for Python + ML)
   - URL: https://railway.app
   - More memory and runtime options

3. **Heroku** (Classic, but still good)
   - URL: https://www.heroku.com
   - Add `Procfile` with: `web: streamlit run src/app/streamlit_app.py`

4. **AWS/Google Cloud/Azure** (Most reliable for production)
   - More expensive but highly scalable
   - Better for handling large ML workloads

## Alternative: Deploy to Render (Recommended)

### Step 1: Create Procfile
Create a file named `Procfile` in the project root:
```
web: streamlit run src/app/streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

### Step 2: Update requirements.txt
```bash
pip freeze > requirements.txt
```

### Step 3: Deploy to Render
1. Go to https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: See Procfile above
6. Deploy!

## Post-Deployment

### Test Your Deployment
- Access your deployed app at the provided URL
- Test cryptocurrency predictions
- Monitor logs for errors

### Monitor & Maintain
```bash
# View deployment logs
vercel logs [deployment-url]

# View environment variables
vercel env ls
```

## Troubleshooting

### Build Fails
- **Solution:** Reduce dependencies in `requirements-vercel.txt`
- Remove: `tensorflow`, `keras`, `torch` (too heavy)

### Timeout Errors
- **Solution:** Use simpler models or cache predictions
- Implement request caching

### Memory Issues
- **Solution:** Deploy on Render or Railway instead
- They offer better memory allocation for ML apps

## Cost Considerations

| Platform | Cost | Best For |
|----------|------|----------|
| Vercel | Free tier (limited) | Static sites, light APIs |
| Render | Free tier + paid | Python ML apps |
| Railway | Pay-as-you-go | Production ML models |
| Heroku | Paid ($7+/month) | Classic Python apps |
| AWS | Pay-as-you-go | Enterprise solutions |

## Quick Reference

### Vercel Deploy Command
```bash
vercel --prod
```

### View Live Logs
```bash
vercel logs [url] --tail
```

### Rollback to Previous Version
```bash
vercel rollback
```

---

**For best results with this ML project, we recommend Render or Railway over Vercel.**
