from django.urls import path
from . import views

urlpatterns = [
    path('',               views.index,          name='index'),
    path('api/info/',      views.video_info,      name='video_info'),
    path('api/download/',  views.download_video,  name='download_video'),
    path('api/file/<str:session_id>/<str:filename>', views.download_file, name='download_file'),
    path('api/cleanup/<str:session_id>', views.cleanup_file, name='cleanup_file'),
]