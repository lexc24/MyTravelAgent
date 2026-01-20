from api.views import CreateUserView
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import (  # ADD THESE IMPORTS
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/user/register", CreateUserView.as_view(), name="register"),
    path("api/token", TokenObtainPairView.as_view(), name="get_token"),
    path("api/token/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("api/", include("api.urls")),  # Include API app URLs
    path("api-auth/", include("rest_framework.urls")),
    path("health", lambda request: HttpResponse("OK")),
    path("destination_search/", include("destination_search.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"
    ),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
