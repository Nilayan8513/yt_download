import os
import re
import json
import uuid
import shutil
import time
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, FileResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse

import yt_dlp

# ── Config ────────────────────────────────────────────────────────────────────

TEMP_DIR    = getattr(settings, 'DOWNLOAD_TEMP_DIR', '/tmp/ytdl_downloads')
FFMPEG_PATH = getattr(settings, 'FFMPEG_PATH', None) \
              or shutil.which('ffmpeg') \
              or '/usr/bin/ffmpeg'

os.makedirs(TEMP_DIR, exist_ok=True)

QUALITY_MAP = {
    '144p':  144,
    '240p':  240,
    '360p':  360,
    '480p':  480,
    '720p':  720,
    '1080p': 1080,
    '1440p': 1440,
    '2160p': 2160,   # 4K
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_ydl_opts() -> dict:
    """
    yt-dlp options that work reliably on Render without cookies or a browser.

    player_client order:
      android_vr  — unlocks 4K (VP9 / AV1) streams without sign-in
      android     — reliable fallback for up to 1080p
      web         — last resort
    """
    return {
        'quiet':                      True,
        'no_warnings':                True,
        'noplaylist':                 True,
        'geo_bypass':                 True,
        'ffmpeg_location':            FFMPEG_PATH,
        'retries':                    5,
        'fragment_retries':           5,
        'skip_unavailable_fragments': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android_vr', 'android', 'web'],
            }
        },
    }


def _resolution_label(height: int) -> str:
    """Map an exact pixel height to the nearest standard label."""
    for h in [144, 240, 360, 480, 720, 1080, 1440, 2160]:
        if height <= h:
            return f'{h}p'
    return f'{height}p'


def _pick_formats(info: dict) -> list:
    """
    Return one entry per standard resolution (144p–2160p), sorted low→high.
    Skips audio-only formats and anything above 4K.
    """
    seen: set = set()
    result: list = []

    for f in info.get('formats', []):
        if f.get('vcodec', 'none') == 'none':
            continue
        height = f.get('height') or 0
        if height <= 0 or height > 2160:
            continue

        label = _resolution_label(height)
        if label in seen:
            continue
        seen.add(label)

        result.append({
            'format_id': f['format_id'],
            'label':     label,
            'height':    height,
            'ext':       f.get('ext', 'mp4'),
            'vcodec':    f.get('vcodec', ''),
            'filesize':  f.get('filesize') or f.get('filesize_approx') or 0,
            'has_audio': f.get('acodec', 'none') != 'none',
        })

    result.sort(key=lambda x: x['height'])
    return result


def _sanitize_filename(name: str) -> str:
    """Strip characters unsafe for Content-Disposition filenames."""
    name = re.sub(r'[^\w\s\-.]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:180]


def _rfc5987_encode(value: str) -> str:
    """Percent-encode a UTF-8 string for use in RFC 5987 filename*=."""
    safe = set(
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        'abcdefghijklmnopqrstuvwxyz'
        '0123456789-._~'
    )
    encoded = ''
    for byte in value.encode('utf-8'):
        c = chr(byte)
        encoded += c if c in safe else f'%{byte:02X}'
    return encoded


def _cleanup_old_files(dir_path: str, max_age_hours: int = 2) -> None:
    """Remove temp files older than max_age_hours to prevent disk bloat."""
    now = time.time()
    try:
        for session_dir in Path(dir_path).iterdir():
            if not session_dir.is_dir():
                continue
            # Check if directory is older than max_age
            age_hours = (now - session_dir.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                shutil.rmtree(session_dir, ignore_errors=True)
    except Exception:
        pass


def _clean_error(msg: str) -> str:
    """Turn raw yt-dlp error strings into user-friendly messages."""
    if 'Sign in' in msg or 'bot' in msg.lower():
        return 'YouTube blocked this request. Please try again in a moment.'
    if 'unavailable' in msg.lower() or 'private' in msg.lower():
        return 'This video is unavailable or private.'
    if 'ffmpeg' in msg.lower():
        return 'ffmpeg not found on the server — please contact the admin.'
    if 'copyright' in msg.lower():
        return 'This video cannot be downloaded due to copyright restrictions.'
    return msg


# ── Views ─────────────────────────────────────────────────────────────────────

def index(request):
    """Serve the single-page frontend."""
    return render(request, 'index.html')


@csrf_exempt
@require_http_methods(['POST'])
def video_info(request):
    """
    POST /api/info/
    Body: { "url": "https://youtube.com/watch?v=..." }

    Returns video metadata + list of available quality options.
    """
    try:
        body = json.loads(request.body)
        url  = body.get('url', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    if not url:
        return JsonResponse({'error': 'URL is required.'}, status=400)

    if 'youtube.com' not in url and 'youtu.be' not in url:
        return JsonResponse({'error': 'Only YouTube URLs are supported.'}, status=400)

    ydl_opts = {**_base_ydl_opts(), 'skip_download': True}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        return JsonResponse({'error': _clean_error(str(e))}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {e}'}, status=500)

    formats = _pick_formats(info)
    best    = formats[-1]['label'] if formats else None   # highest available quality

    return JsonResponse({
        'title':        info.get('title', 'Unknown'),
        'thumbnail':    info.get('thumbnail', ''),
        'duration':     info.get('duration', 0),
        'uploader':     info.get('uploader', ''),
        'view_count':   info.get('view_count', 0),
        'formats':      formats,
        'best_quality': best,   # original upload quality (auto-selected in UI)
        'url':          url,
    })


@csrf_exempt
@require_http_methods(['POST'])
def download_video(request):
    """
    POST /api/download/
    Body: {
        "url":        "https://youtube.com/watch?v=...",
        "quality":    "2160p",
        "audio_only": false
    }

    Returns JSON with download_url that browser can use to fetch the file.
    File is stored temporarily on server and auto-cleaned after 2 hours.
    """
    try:
        body       = json.loads(request.body)
        url        = body.get('url', '').strip()
        quality    = body.get('quality', '1080p')
        audio_only = bool(body.get('audio_only', False))
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    if not url:
        return JsonResponse({'error': 'URL is required.'}, status=400)

    # Cleanup old files periodically
    _cleanup_old_files(TEMP_DIR, max_age_hours=2)

    max_height = QUALITY_MAP.get(quality, 1080)

    # Create session directory
    session_id = uuid.uuid4().hex
    output_dir = os.path.join(TEMP_DIR, session_id)
    os.makedirs(output_dir, exist_ok=True)

    # ── Format selector ───────────────────────────────────────────────────────
    if audio_only:
        fmt_selector   = 'bestaudio/best'
        postprocessors = [{
            'key':              'FFmpegExtractAudio',
            'preferredcodec':   'mp3',
            'preferredquality': '320',
        }]
        merge_fmt = None
    else:
        fmt_selector = (
            f'bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]'
            f'/bestvideo[height<={max_height}][ext=webm]+bestaudio[ext=webm]'
            f'/bestvideo[height<={max_height}]+bestaudio'
            f'/best[height<={max_height}]'
        )
        postprocessors = []
        merge_fmt      = 'mp4'

    ydl_opts = {
        **_base_ydl_opts(),
        'format':              fmt_selector,
        'outtmpl':             os.path.join(output_dir, 'video.%(ext)s'),
        'postprocessors':      postprocessors,
        'merge_output_format': merge_fmt or 'mp4',
    }

    # ── Download ──────────────────────────────────────────────────────────────
    title = 'video'
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info  = ydl.extract_info(url, download=True)
            title = (info or {}).get('title', 'video')
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        return JsonResponse({'error': _clean_error(str(e))}, status=400)
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        return JsonResponse({'error': f'Unexpected error: {e}'}, status=500)

    # ── Find the output file ──────────────────────────────────────────────────
    files = sorted(
        [p for p in Path(output_dir).iterdir() if p.is_file()],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not files:
        shutil.rmtree(output_dir, ignore_errors=True)
        return JsonResponse({'error': 'No output file was produced.'}, status=500)

    filepath  = files[0]
    ext       = filepath.suffix.lower()
    file_size = filepath.stat().st_size

    # Return download URL for browser to fetch
    download_url = reverse('download_file', args=[session_id, filepath.name])
    safe_title  = _sanitize_filename(title)
    
    return JsonResponse({
        'success': True,
        'filename': f'{safe_title}{ext}',
        'size': file_size,
        'download_url': download_url,
        'file_id': session_id,
    })


@csrf_exempt
@require_http_methods(['GET'])
def download_file(request, session_id, filename):
    """
    GET /api/file/<session_id>/<filename>
    
    Serves the prepared download file directly to browser.
    Browser can pause/resume natively.
    """
    filepath = Path(TEMP_DIR) / session_id / filename
    
    # Security: ensure path is within TEMP_DIR
    try:
        filepath = filepath.resolve()
        temp_dir = Path(TEMP_DIR).resolve()
        if not str(filepath).startswith(str(temp_dir)):
            return JsonResponse({'error': 'Invalid file path'}, status=403)
    except Exception:
        return JsonResponse({'error': 'Invalid file path'}, status=403)
    
    if not filepath.exists():
        return JsonResponse({'error': 'File not found'}, status=404)

    ext = filepath.suffix.lower()
    mime_type = 'audio/mpeg' if ext == '.mp3' else 'video/mp4'

    response = FileResponse(
        open(filepath, 'rb'),
        content_type=mime_type,
        as_attachment=True,
        filename=filename,
    )
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@require_http_methods(['POST'])
def cleanup_file(request, session_id):
    """
    POST /api/cleanup/<session_id>
    
    Manually cleanup a file (called after successful download).
    """
    output_dir = Path(TEMP_DIR) / session_id
    
    try:
        output_dir = output_dir.resolve()
        temp_dir = Path(TEMP_DIR).resolve()
        if not str(output_dir).startswith(str(temp_dir)):
            return JsonResponse({'error': 'Invalid path'}, status=403)
    except Exception:
        return JsonResponse({'error': 'Invalid path'}, status=403)
    
    shutil.rmtree(output_dir, ignore_errors=True)
    return JsonResponse({'success': True})