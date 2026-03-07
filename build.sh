#!/usr/bin/env bash
set -o errexit

# 1. Install ffmpeg — required for merging separate video+audio streams (4K, 1440p, 1080p)
apt-get update -qq && apt-get install -y -qq ffmpeg

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Always pull the latest yt-dlp — YouTube breaks older versions frequently
pip install -U yt-dlp

# 4. Collect static files for WhiteNoise to serve
python manage.py collectstatic --no-input