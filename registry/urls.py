from django.urls import path

from . import views

app_name = "registry"
urlpatterns = [
    path("", views.grid_list, name="grid_list"),
    path("owners/", views.owner_list, name="owner_list"),
    path("owners/new/", views.new_owner, name="new_owner"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/new/", views.new_session, name="new_session"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("deleted-grids/", views.deleted_grid_list, name="deleted_grid_list"),
    path("deleted-grids/<int:pk>/", views.deleted_grid_detail, name="deleted_grid_detail"),
    path("grids/<int:pk>/delete/", views.grid_delete, name="grid_delete"),
    path("grids/<int:pk>/", views.grid_detail, name="grid_detail"),
]
