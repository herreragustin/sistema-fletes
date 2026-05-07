from django.urls import path

from . import views


app_name = "importadores"

urlpatterns = [
    path("", views.lista_legacy_dbf, name="lista_legacy_dbf"),
    path("dbf/", views.detalle_legacy_dbf, name="detalle_legacy_dbf"),
]
