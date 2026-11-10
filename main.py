"""
Facebook Video Downloader API — FastAPI + yt-dlp
Returns metadata + direct download links (no file proxying — fits free tier).
"""
import asyncio
import json
import sys
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="FB Video Downloader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend domain in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

FB_HOSTS = {
    "facebook.com", "www.facebook.com", "m.facebook.com",
    "web.facebook.com", "fb.watch", "www.fb.watch", "fb.gg",
}

QUALITY_MAP = {
    "hd": "best[ext=mp4]/best",
    "sd": "worst[ext=mp4][height>360]/worst[ext=mp4]/worst",
}


def validate_url(url: str) -> str:
    try:
        p = urlparse(url)
    except Exception:
        raise HTTPException(400, "Invalid URL")
    if p.scheme not in ("http", "https"):
        raise HTTPException(400, "URL must start with http(s)://")
    host = (p.hostname or "").lower()
    if host not in FB_HOSTS:
        raise HTTPException(400, f"Not a Facebook URL (got host: {host})")
    return url


async def run_ytdlp(url: str, mode: str) -> dict:
    """Run yt-dlp in JSON-dump mode. Public videos only."""
    cmd = [
        sys.executable, "-m", "yt_dlp",  # module form: finds yt-dlp wherever pip put it (venv, Render runtime, etc.)
        "--dump-single-json", "--no-warnings",
        "--no-playlist", "--socket-timeout", "20",
        "-f", QUALITY_MAP.get(mode, QUALITY_MAP["hd"]),
        url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        raise HTTPException(504, "yt-dlp timed out fetching this video")
    if proc.returncode != 0:
        msg = err.decode(errors="ignore").strip().splitlines()
        tail = msg[-1] if msg else "unknown yt-dlp error"
        if "Private video" in tail or "login" in tail.lower():
            raise HTTPException(403, "Video is private or requires login — public videos only")
        raise HTTPException(422, f"yt-dlp failed: {tail[:300]}")
    return json.loads(out.decode())


def pick_formats(info: dict) -> list:
    """Flatten yt-dlp formats into clean download links."""
    results = []
    seen = set()
    for f in info.get("formats") or []:
        if not f.get("url") or f.get("vcodec") == "none":
            continue
        if f.get("protocol") not in ("https", "http"):
            continue
        key = (f.get("format_id"), f.get("height"))
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "quality": f"{f.get('height', '?')}p" if f.get("height") else f.get("format_note", "unknown"),
            "ext": f.get("ext"),
            "size_mb": round(f["filesize"] / 1e6, 1) if f.get("filesize") else None,
            "url": f["url"],  # signed fbcdn link — expires, use immediately
        })
    # highest quality first
    results.sort(key=lambda x: (x["quality"] != "unknown", str(x["quality"])), reverse=True)
    return results[:6]


@app.get("/")
def root():
    return {"service": "fbdl-api", "usage": "GET /api/download?url=<facebook_video_url>&quality=hd"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/download")
async def download(
    url: str = Query(..., description="Facebook video/reel/fb.watch URL"),
    quality: str = Query("hd", pattern="^(hd|sd)$"),
):
    url = validate_url(url)
    info = await run_ytdlp(url, quality)
    return JSONResponse({
        "success": True,
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration_seconds": info.get("duration"),
        "uploader": info.get("uploader"),
        "webpage_url": info.get("webpage_url"),
        "requested_quality": quality,
        "downloads": pick_formats(info),
        "note": "Links are signed by Facebook CDN and expire quickly. Use immediately.",
    })


@app.exception_handler(Exception)
async def unhandled(request, exc):
    return JSONResponse({"success": False, "error": str(exc)[:300]}, status_code=500)
