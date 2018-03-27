"""Cloudigrade URL Configuration."""
from django.conf.urls import url
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions, routers

from account.views import AccountViewSet, ReportViewSet

router = routers.DefaultRouter()
router.register(r'account', AccountViewSet)
router.register(r'report', ReportViewSet, base_name='report')

schema_view = get_schema_view(
    openapi.Info(
        title='Cloudigrade API',
        default_version='v1',
        description='REST Endpoints for Cloudigrade Core',
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls')),
    path('admin/', admin.site.urls),
    url(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=None), name='schema-json'),
    url(r'^swagger/$',
        schema_view.with_ui('swagger', cache_timeout=None),
        name='schema-swagger-ui'),
    url(r'^redoc/$',
        schema_view.with_ui('redoc', cache_timeout=None), name='schema-redoc'),
]
