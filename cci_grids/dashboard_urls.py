"""Root-mounted URL configuration used only by the dashboard descriptor."""

from django.urls import include, path

urlpatterns = [path("registry/", include("cci_grids.urls"))]
