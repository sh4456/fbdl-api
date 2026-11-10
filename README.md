# FB Video Downloader API

FastAPI + yt-dlp. Returns metadata + direct signed download links for public Facebook videos (watch/videos/reels/fb.watch). No file proxying — built for Render's free tier (0.1 CPU / 512MB).

## Verified working
`GET /api/download?url=https://www.facebook.com/watch/?v=10153231379946729` → returns title, duration, uploader, and SD + HD mp4 links from fbcdn.net (signed, expire quickly).

## Endpoints
- `GET /` — usage info
- `GET /health` — health check (used by Render)
- `GET /api/download?url=<fb_url>&quality=hd|sd` — metadata + download links

Errors: `400` non-Facebook URL · `403` private/login-required video · `422` yt-dlp extraction failure · `504` fetch timeout.

## Run locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PORT=8077 .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8077
```

## Deploy on Render (free)
1. Push this folder to a GitHub repo.
2. Render Dashboard → **New → Web Service** → connect the repo.
3. Runtime: **Python 3** · Plan: **Free**
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `bash start.sh`
6. (Optional) add `render.yaml` blueprint instead — it's included.
7. Deploy. URL: `https://<service-name>.onrender.com`

## Notes
- **ffmpeg is preinstalled in Render's Python runtime** (official docs) — no install needed.
- `yt-dlp` is unpinned in requirements.txt so each deploy pulls the latest — **redeploy weekly** to keep extraction working as Facebook changes.
- Only **public** videos resolve; friends-only/group/private will 403.
- `fb.watch` short links work (yt-dlp follows redirects).
- Signed fbcdn links expire — return them to the user immediately, don't cache.
- CORS is open (`*`) — restrict `allow_origins` to your frontend before sharing publicly.
