# YT Vault — 4K YouTube Downloader

A clean, fast Django web application that lets you download YouTube videos in any quality from 144p all the way up to 4K (2160p), or extract audio as high-quality MP3 files.

---

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Deployment (Render)](#deployment-render)
- [How It Works](#how-it-works)
- [Notes & Limitations](#notes--limitations)

---

## Features

- **Multiple quality options** — Download videos at 144p, 240p, 360p, 480p, 720p, 1080p, 1440p (2K), or 2160p (4K)
- **Audio extraction** — Download audio only as MP3 at 320 kbps
- **Auto quality detection** — Fetches available formats and highlights the original upload quality
- **Server-side processing** — ffmpeg merges separate video + audio streams for high-resolution downloads
- **Auto cleanup** — Temporary files are removed from the server after 2 hours (or immediately after the browser download completes)
- **Responsive dark UI** — Works on desktop and mobile browsers
- **No sign-in required** — Uses yt-dlp's `android_vr` client to access streams without authentication

---

## Screenshots

The app presents a single-page interface:

1. **Paste** a YouTube URL into the input field and click **Fetch**
2. The app retrieves the video thumbnail, title, uploader, duration, and available quality options
3. **Select** a quality pill (the original upload quality is auto-selected and labelled `ORIG`)
4. Optionally toggle **Audio only** for an MP3 download
5. Click **Download** — the server prepares the file and the browser download starts automatically

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | [Django 4.2](https://docs.djangoproject.com/en/4.2/) |
| Video downloading | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| Audio/video merging | [ffmpeg](https://ffmpeg.org/) |
| Static file serving | [WhiteNoise](https://whitenoise.readthedocs.io/) |
| Production server | [Gunicorn](https://gunicorn.org/) |
| Frontend | Vanilla HTML / CSS / JavaScript (no framework) |

---

## Project Structure

```
yt_download/
├── youtube_downloader/       # Django project package
│   ├── settings.py           # Project settings (env-configurable)
│   ├── urls.py               # Root URL configuration
│   ├── wsgi.py               # WSGI entry point
│   └── asgi.py               # ASGI entry point
├── ytdl_app/                 # Main application
│   ├── templates/
│   │   └── index.html        # Single-page frontend
│   ├── views.py              # All API endpoints and download logic
│   ├── urls.py               # App-level URL routing
│   ├── models.py             # (No database models used)
│   └── tests.py              # Test suite
├── manage.py                 # Django management script
├── Requirement.txt           # Python dependencies
├── build.sh                  # Build script for Render deployment
└── .gitignore
```

---

## Prerequisites

- Python 3.10 or later
- `ffmpeg` installed and on your `PATH` (required for 1080p and above)
  - **Ubuntu/Debian**: `sudo apt-get install ffmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/Nilayan8513/yt_download.git
cd yt_download
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r Requirement.txt
# Always keep yt-dlp at the latest version — YouTube breaks older versions frequently
pip install -U yt-dlp
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Run the development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Configuration

All settings can be overridden with environment variables.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure dev key | Django secret key — **must** be changed for production |
| `DEBUG` | `True` | Set to `False` in production |
| `DOWNLOAD_TEMP_DIR` | `<BASE_DIR>/temp_downloads` | Directory used for temporary download files |
| `FFMPEG_PATH` | auto-detected via `which ffmpeg` | Explicit path to the `ffmpeg` binary |

For local development you can create a `.env` file (it is in `.gitignore`) and load it with a tool like [`python-dotenv`](https://github.com/theskumar/python-dotenv), or simply export variables in your shell:

```bash
export SECRET_KEY="your-very-secret-key"
export DEBUG="False"
```

---

## API Reference

All endpoints are served by `ytdl_app`.

### `GET /`

Serves the single-page frontend (`index.html`).

---

### `POST /api/info/`

Fetches video metadata and the list of available download qualities.

**Request body (JSON)**

```json
{ "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }
```

**Response (200)**

```json
{
  "title":        "Video title",
  "thumbnail":    "https://i.ytimg.com/vi/.../maxresdefault.jpg",
  "duration":     212,
  "uploader":     "Channel name",
  "view_count":   1400000000,
  "best_quality": "1080p",
  "url":          "https://www.youtube.com/watch?v=...",
  "formats": [
    { "format_id": "...", "label": "360p",  "height": 360,  "ext": "mp4", "vcodec": "avc1...", "filesize": 12345678, "has_audio": true },
    { "format_id": "...", "label": "720p",  "height": 720,  "ext": "mp4", "vcodec": "avc1...", "filesize": 34567890, "has_audio": false },
    { "format_id": "...", "label": "1080p", "height": 1080, "ext": "mp4", "vcodec": "avc1...", "filesize": 56789012, "has_audio": false }
  ]
}
```

**Error response (400)**

```json
{ "error": "Only YouTube URLs are supported." }
```

---

### `POST /api/download/`

Downloads the video (or audio) on the server and returns a URL the browser can use to fetch the file.

**Request body (JSON)**

```json
{
  "url":        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "quality":    "1080p",
  "audio_only": false
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | string | — | YouTube video URL (required) |
| `quality` | string | `"1080p"` | One of `144p`, `240p`, `360p`, `480p`, `720p`, `1080p`, `1440p`, `2160p` |
| `audio_only` | boolean | `false` | When `true`, extracts MP3 audio at 320 kbps and ignores `quality` |

**Response (200)**

```json
{
  "success":      true,
  "filename":     "Video_title.mp4",
  "size":         56789012,
  "download_url": "/api/file/<session_id>/video.mp4",
  "file_id":      "<session_id>"
}
```

**Error response (400 / 500)**

```json
{ "error": "YouTube blocked this request. Please try again in a moment." }
```

---

### `GET /api/file/<session_id>/<filename>`

Serves the prepared file as a binary download (`Content-Disposition: attachment`). This URL is returned by `/api/download/` and is what the browser navigates to when saving the file.

- Returns `404` if the file no longer exists (e.g., already cleaned up).
- Returns `403` if the resolved path falls outside `DOWNLOAD_TEMP_DIR` (path traversal protection).

---

### `POST /api/cleanup/<session_id>`

Manually deletes the temporary session directory created by `/api/download/`. The frontend calls this automatically ~10 seconds after the browser download starts.

**Response (200)**

```json
{ "success": true }
```

---

## Deployment (Render)

The repository includes a `build.sh` script designed for [Render](https://render.com/) web services.

### Steps

1. Create a new **Web Service** on Render and connect this repository.

2. Set the following in the Render dashboard (**Settings → Environment**):

   | Key | Value |
   |---|---|
   | `SECRET_KEY` | A long random string |
   | `DEBUG` | `False` |

3. Configure the service:
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn youtube_downloader.wsgi:application`

4. Render will automatically:
   - Install `ffmpeg` (needed for stream merging)
   - Install all Python dependencies
   - Update `yt-dlp` to the latest version
   - Collect static files for WhiteNoise

> **Important**: On Render's free tier the ephemeral disk is cleared on each deploy. Temporary download files are stored in `/tmp/ytdl_downloads` by default and are removed automatically anyway, so no persistent disk is required.

---

## How It Works

```
Browser                      Django Server                    YouTube
  │                               │                               │
  │── POST /api/info/ ──────────>│                               │
  │                               │── yt-dlp extract_info() ───>│
  │                               │<── video metadata ──────────│
  │<── JSON (formats, title…) ──│                               │
  │                               │                               │
  │── POST /api/download/ ──────>│                               │
  │                               │── yt-dlp download() ────────>│
  │                               │<── video + audio streams ───│
  │                               │── ffmpeg merge ──────────────│
  │<── JSON (download_url) ─────│                               │
  │                               │                               │
  │── GET /api/file/<id>/… ─────>│                               │
  │<── binary file stream ──────│                               │
  │                               │                               │
  │── POST /api/cleanup/<id> ───>│                               │
  │<── { success: true } ───────│ (temp files deleted)          │
```

**Quality selection** uses yt-dlp's format selector. For videos above 720p, YouTube serves separate video-only and audio-only streams. ffmpeg merges them into a single `.mp4` file on the server before the browser download begins.

**Error handling** translates raw yt-dlp error strings into friendly user-facing messages covering: bot/sign-in blocks, unavailable/private videos, missing ffmpeg, and copyright restrictions.

---

## Notes & Limitations

- **Personal use only** — Respect YouTube's Terms of Service. Only download content you have the right to download.
- **Copyright** — Do not download content that is protected by copyright without permission from the rights holder.
- **Rate limiting** — YouTube may throttle or block repeated requests from the same IP. If you see "YouTube blocked this request", wait a moment and try again.
- **yt-dlp freshness** — YouTube frequently changes its internal APIs. If downloads stop working, run `pip install -U yt-dlp` to get the latest extractor fixes.
- **4K availability** — 4K streams are only available on videos that were originally uploaded in 4K. The UI marks the original upload quality with an `ORIG` badge.
- **File size** — Large files (4K, long videos) may take a minute or more to process on the server before the browser download begins.
