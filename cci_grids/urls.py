from django.urls import path

from . import administration, excel_views, grid_storage_views, storage_views, views
from .facility_time import facility_view


def route(pattern, view, **kwargs):
    return path(pattern, facility_view(view), **kwargs)


app_name = "registry"
urlpatterns = [
    route("pucks/<int:pk>/", storage_views.puck_detail, name="puck_detail"),
    route("pucks/", storage_views.puck_inventory, name="puck_inventory"),
    route("grids/<int:pk>/storage/", grid_storage_views.grid_storage, name="grid_storage"),
    route("inventory/", storage_views.inventory, name="inventory"),
    route("inventory/<int:pk>/", storage_views.box_detail, name="box_detail"),
    route("", views.grid_list, name="grid_list"),
    route("export/", excel_views.excel_export, name="excel_export"),
    route("import/", excel_views.excel_import, name="excel_import"),
    route("import/template/", excel_views.excel_template, name="excel_template"),
    route("owners/", views.owner_list, name="owner_list"),
    route("owners/export/", excel_views.owner_excel_export, name="owner_excel_export"),
    route("owners/new/", views.new_owner, name="new_owner"),
    route("owners/<int:pk>/edit/", administration.owner_edit, name="owner_edit"),
    route("owners/<int:pk>/grants/", administration.owner_grants, name="owner_grants"),
    route("owner-grants/<int:pk>/edit/", administration.owner_grant_edit, name="owner_grant_edit"),
    route("sessions/", views.session_list, name="session_list"),
    route("sessions/export/", excel_views.session_excel_export, name="session_excel_export"),
    route("sessions/new/", views.new_session, name="new_session"),
    route("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    route("deleted-grids/", views.deleted_grid_list, name="deleted_grid_list"),
    route("discarded-grids/", views.discarded_grid_list, name="discarded_grid_list"),
    route("transferred-grids/", views.transferred_grid_list, name="transferred_grid_list"),
    route("deleted-grids/<int:pk>/", views.deleted_grid_detail, name="deleted_grid_detail"),
    route("grids/<int:pk>/delete/", views.grid_delete, name="grid_delete"),
    route("grids/<int:pk>/", views.grid_detail, name="grid_detail"),
]
