from django.urls import path

from . import excel_views, grid_storage_views, storage_views, views

app_name = "registry"
urlpatterns = [
    path("pucks/<int:pk>/", storage_views.puck_detail, name="puck_detail"),
    path("pucks/", storage_views.puck_inventory, name="puck_inventory"),
    path("grids/<int:pk>/storage/", grid_storage_views.grid_storage, name="grid_storage"),
    path("inventory/", storage_views.inventory, name="inventory"),
    path("inventory/<int:pk>/", storage_views.box_detail, name="box_detail"),
    path("", views.grid_list, name="grid_list"),
    path("export/", excel_views.excel_export, name="excel_export"),
    path("import/", excel_views.excel_import, name="excel_import"),
    path("import/template/", excel_views.excel_template, name="excel_template"),
    path("owners/", views.owner_list, name="owner_list"),
    path("owners/export/", excel_views.owner_excel_export, name="owner_excel_export"),
    path("owners/new/", views.new_owner, name="new_owner"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/export/", excel_views.session_excel_export, name="session_excel_export"),
    path("sessions/new/", views.new_session, name="new_session"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("deleted-grids/", views.deleted_grid_list, name="deleted_grid_list"),
    path("deleted-grids/<int:pk>/", views.deleted_grid_detail, name="deleted_grid_detail"),
    path("grids/<int:pk>/delete/", views.grid_delete, name="grid_delete"),
    path("grids/<int:pk>/", views.grid_detail, name="grid_detail"),
]
