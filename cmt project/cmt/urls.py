"""
URL configuration for cmt project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView
from django.http import JsonResponse


urlpatterns = [
    path('health/', lambda r: JsonResponse({'status': 'ok'})),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/', include('api.urls')),
]

urlpatterns += i18n_patterns(
    path('', RedirectView.as_view(pattern_name='home_redirect', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('conference/', include('conference.urls')),
    path('membership/', include('membership.urls')),
    path('submissions/', include('submissions.urls')),
    path('review/', include('review.urls')),
    path('schedule/', include('schedule.urls')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
