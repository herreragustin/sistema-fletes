from django.urls import path

from . import views


app_name = "importadores"

urlpatterns = [
    path("", views.panel_sistema_anterior, name="panel_sistema_anterior"),
    path("clientes/", views.lista_clientes_historicos, name="lista_clientes_historicos"),
    path("clientes/<int:pk>/", views.detalle_cliente_historico, name="detalle_cliente_historico"),
    path("choferes/", views.lista_choferes_historicos, name="lista_choferes_historicos"),
    path("choferes/<int:pk>/", views.detalle_chofer_historico, name="detalle_chofer_historico"),
    path("viajes/", views.lista_viajes_historicos, name="lista_viajes_historicos"),
    path("viajes/<int:pk>/", views.detalle_viaje_historico, name="detalle_viaje_historico"),
    path("reservas/", views.lista_reservas_historicas, name="lista_reservas_historicas"),
    path("reservas/<int:pk>/", views.detalle_reserva_historica, name="detalle_reserva_historica"),
    path("dbf/", views.lista_legacy_dbf, name="lista_legacy_dbf"),
    path("dbf/detalle/", views.detalle_legacy_dbf, name="detalle_legacy_dbf"),
]
