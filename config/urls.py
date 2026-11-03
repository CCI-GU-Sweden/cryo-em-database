from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.views import home

urlpatterns = [
    path("", home, name="home"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    # Django's logout view requires POST, preventing accidental logout by a link.
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
