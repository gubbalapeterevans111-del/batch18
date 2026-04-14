# Deployment Guide

## ⚠️ Important Note About Free Servers (Vercel / Render)
 Vercel is amazing for website frontends, **it will not work for this face detection system**. 

Here is why:
1. **Size Limits**: Vercel Serverless Functions have a strict size limit of 50MB (uncompressed 250MB). The `insightface` AI model along with `opencv` and `onnxruntime` takes up over **1.5 GB** of space.
2. **Timeout Limits**: Vercel free tier shuts down any script that takes longer than 10 seconds. Downloading photos from Google Drive and scanning them takes much longer than 10 seconds.
3. **RAM Limits**: Free servers like Render give you 512MB RAM. Insightface needs at least 1-2 GB of RAM to run effectively. It will crash with an "Out of Memory" error.

## ✅ The Solution: Hugging Face Spaces (100% Free)
Hugging Face Spaces is a free hosting platform specifically designed for heavy Machine Learning apps like yours! It gives you **16GB of RAM** and **50GB of disk space** for free.

Here is how you can deploy your code there:

### Step 1: Create a Hugging Face Account
Go to [huggingface.co](https://huggingface.co) and create a free account.

### Step 2: Create a New Space
1. Click on **Spaces** at the top, then **Create new Space**.
2. Give it a name (e.g., `wedding-face-search`).
3. Choose **Docker** as the Space SDK.
4. Choose **Blank** template.
5. Click **Create Space**.

### Step 3: Upload Your Files
Upload the files from this folder directly into your Hugging Face Space repository:
- `app.py`
- `main.py`
- `downloader.py`
- `face_engine.py`
- `camera.py`
- `requirements.txt`
- `Dockerfile` 
- `templates/` (folder)
- `static/` (folder)

### Step 4: Wait for Build
Once you upload everything, Hugging Face will automatically Build and Run your app using the `Dockerfile` I prepared. It will be available at a public link for anyone to use!
