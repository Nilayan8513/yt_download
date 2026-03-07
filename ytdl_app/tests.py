from django.test import TestCase

# Create your tests here.
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client


class VideoInfoViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

    def test_missing_url_returns_400(self):
        res = self.client.post(
            '/api/info/',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.json())

    def test_non_youtube_url_returns_400(self):
        res = self.client.post(
            '/api/info/',
            data=json.dumps({'url': 'https://vimeo.com/123456'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('Only YouTube', res.json()['error'])

    def test_invalid_json_returns_400(self):
        res = self.client.post(
            '/api/info/',
            data='not-json',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    @patch('ytdl_app.views.yt_dlp.YoutubeDL')
    def test_valid_url_returns_metadata(self, mock_ydl_class):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'title':      'Test Video',
            'thumbnail':  'https://img.youtube.com/thumb.jpg',
            'duration':   213,
            'uploader':   'Test Channel',
            'view_count': 1000000,
            'formats': [
                {
                    'format_id': '137',
                    'vcodec':    'avc1',
                    'acodec':    'none',
                    'height':    1080,
                    'ext':       'mp4',
                    'filesize':  500_000_000,
                },
                {
                    'format_id': '313',
                    'vcodec':    'vp9',
                    'acodec':    'none',
                    'height':    2160,
                    'ext':       'webm',
                    'filesize':  2_000_000_000,
                },
            ],
        }

        res = self.client.post(
            '/api/info/',
            data=json.dumps({'url': self.url}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['title'], 'Test Video')
        self.assertIn('formats', data)
        self.assertEqual(data['best_quality'], '2160p')


class DownloadViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

    def test_missing_url_returns_400(self):
        res = self.client.post(
            '/api/download/',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_invalid_json_returns_400(self):
        res = self.client.post(
            '/api/download/',
            data='bad',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)