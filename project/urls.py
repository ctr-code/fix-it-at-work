from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('profile', core_views.profile, name='profile'),
    path('', include('cases.urls')),
]
# Uploads are not served from /media/: every photo and voice note goes through /files/, which checks the
# person may see the case (cases/files.py).
