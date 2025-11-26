from django.http import JsonResponse
from . import views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import login_view

urlpatterns = [
    path('ping/', views.ping),
    path('base/', views.base_view, name='base_view'),
    path('admin/', admin.site.urls),
    path('', login_view, name='login'),
    path('', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('clients/', include('clients.urls')),
    path('sales/', include('sales.urls')),
    path('dashboard/', include('dashboard.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
