# YT ✦ JOURNAL — Deploy Guide (हिंदी + English)

YouTube link → PDF journal banane wala app. Isko online karne ke 3 aasaan tarike:

---

## ⭐ Option 1: Render.com (FREE — sabse aasaan, recommended)

### Step 1 — Code ko GitHub par daalo
1. https://github.com par account banao (agar nahi hai)
2. New Repository → naam do `yt-journal` → Create
3. Apne computer par is folder me terminal kholo aur:
   ```bash
   git init
   git add .
   git commit -m "yt journal app"
   git branch -M main
   git remote add origin https://github.com/APNA_USERNAME/yt-journal.git
   git push -u origin main
   ```
   (Ya GitHub website par "uploading an existing file" se saari files drag-drop kar do)

### Step 2 — Render par deploy karo
1. https://render.com par jao → **Sign up with GitHub**
2. Dashboard → **New +** → **Web Service**
3. Apni `yt-journal` repository select karo
4. Settings aise bharo:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free
5. **Create Web Service** dabao — 2-3 minute me build hoga
6. Ho gaya! 🎉 Aapko URL milega: `https://yt-journal.onrender.com`

> Note: Free plan par 15 min koi na aaye to app so jaata hai,
> agla visitor aane par ~30 sec me wapas jag jaata hai.

---

## Option 2: Railway.app (thoda aur fast, $5 free credit)

1. https://railway.app → Login with GitHub
2. **New Project** → **Deploy from GitHub repo** → `yt-journal` chuno
3. Railway khud sab detect kar lega (Procfile included hai)
4. Settings → **Generate Domain** → aapka public URL ready

---

## Option 3: PythonAnywhere (free, GitHub ki zaroorat nahi)

1. https://www.pythonanywhere.com → free account banao
2. **Files** tab me saari files upload karo (ya zip upload karke unzip)
3. **Consoles** → Bash console kholo:
   ```bash
   pip install --user -r yt-journal/requirements.txt
   ```
4. **Web** tab → **Add a new web app** → Flask → apna `app.py` point karo
5. URL milega: `https://APNA_USERNAME.pythonanywhere.com`

---

## ⚠️ Ek zaroori baat — Transcript blocking

YouTube kabhi-kabhi **cloud server ke IP** se transcript requests block kar deta hai
(app chalega, PDF banega, bas transcript page par "no transcript" aa sakta hai).

Agar aisa ho to fix: **Webshare** jaise proxy service (free tier available):

```python
# app.py me sabse upar:
from youtube_transcript_api.proxies import WebshareProxyConfig

# get_transcript() ke andar YouTubeTranscriptApi() ki jagah:
api = YouTubeTranscriptApi(
    proxy_config=WebshareProxyConfig(
        proxy_username="WEBSHARE_USERNAME",
        proxy_password="WEBSHARE_PASSWORD",
    )
)
```

Pehle bina proxy ke deploy karke test karo — bahut baar bina proxy ke bhi chal jaata hai.

---

## Files in this project

| File               | Kaam                                    |
|--------------------|-----------------------------------------|
| `app.py`           | Flask backend + PDF engine               |
| `templates/index.html` | Chrome/Y2K 3D front-end             |
| `fonts/`           | Bundled fonts (PDF ke liye)              |
| `requirements.txt` | Python dependencies                      |
| `Procfile`         | Railway/Heroku start command             |
| `render.yaml`      | Render one-click config                  |
