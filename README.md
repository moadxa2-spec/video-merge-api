# 🎬 Video Merge API

A free, self-hostable video merging API built with FastAPI + FFmpeg.  
Deploy on **Render (free tier)** and call it from **n8n** just like Fal.ai.

---

## 🚀 Deploy on Render (Free)

### Step 1 — Push to GitHub
1. Create a new GitHub repo (e.g. `video-merge-api`)
2. Upload all files: `main.py`, `requirements.txt`, `Dockerfile`, `render.yaml`

### Step 2 — Deploy on Render
1. Go to [render.com](https://render.com) and sign up free
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Render auto-detects the `Dockerfile` ✅
5. Set:
   - **Name:** `video-merge-api`
   - **Plan:** Free
6. Click **Deploy**

Your API will be live at:
```
https://video-merge-api.onrender.com
```

---

## 📡 API Endpoints

### `GET /`
Health check — returns API status.

### `POST /merge`
Merge multiple videos into one.

**Request body:**
```json
{
  "videos": [
    "https://example.com/video1.mp4",
    "https://example.com/video2.mp4",
    "https://example.com/video3.mp4"
  ]
}
```

**Response:** Returns the merged `.mp4` file directly as a download.

---

## 🔧 Use in n8n

### Workflow Setup:
1. After your 3 Veo video nodes, add a **Code node** to collect the URLs:
```javascript
return [{
  json: {
    videos: [
      $('Veo Video 1').item.json.videoUrl,
      $('Veo Video 2').item.json.videoUrl,
      $('Veo Video 3').item.json.videoUrl
    ]
  }
}];
```

2. Add an **HTTP Request node**:
   - **Method:** POST
   - **URL:** `https://your-app.onrender.com/merge`
   - **Body Type:** JSON
   - **Body:**
   ```json
   {
     "videos": {{ $json.videos }}
   }
   ```
   - **Response Format:** File

3. The node returns the merged video binary — save it or upload it anywhere!

---

## ⚠️ Render Free Tier Notes

| Limit | Free Tier |
|-------|-----------|
| RAM | 512MB |
| CPU | Shared |
| Bandwidth | 100GB/month |
| Sleep after inactivity | 15 minutes (first request wakes it up) |

> 💡 **Tip:** If the app is sleeping, the first request may take ~30 seconds to wake up. Add a **Wait node** (30s) in n8n before calling the API if needed.

---

## 🛠 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install FFmpeg (Mac)
brew install ffmpeg

# Install FFmpeg (Ubuntu)
sudo apt install ffmpeg

# Run the API
uvicorn main:app --reload --port 8000
```

Test it:
```bash
curl -X POST http://localhost:8000/merge \
  -H "Content-Type: application/json" \
  -d '{"videos": ["https://url1.mp4", "https://url2.mp4", "https://url3.mp4"]}' \
  --output merged.mp4
```
