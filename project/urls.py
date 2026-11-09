from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('profile', core_views.profile, name='profile'),
    path('', include('cases.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
