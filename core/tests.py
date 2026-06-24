from datetime import date, time
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import FleteForm
from .models import Chofer, Cliente, Flete


class FleteFormFechaHoraActualTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre="Cliente prueba",
            telefono="1111111111",
            direccion="Origen guardado",
        )
        self.chofer = Chofer.objects.create(
            nombre="Chofer prueba",
            telefono="2222222222",
            dni="33333333",
            patente="ABC123",
        )

    def test_nuevo_flete_precarga_fecha_y_hora_actual_editables(self):
        ahora_local = timezone.datetime(
            2026, 6, 24, 15, 47, 31, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")
        )

        with patch("core.forms.timezone.localtime", return_value=ahora_local):
            form = FleteForm()

        self.assertEqual(form.initial["fecha"], date(2026, 6, 24))
        self.assertEqual(form.initial["hora_inicio"], time(15, 47))
        self.assertFalse(form.fields["fecha"].disabled)
        self.assertFalse(form.fields["hora_inicio"].disabled)

    def test_edicion_no_pisa_fecha_y_hora_guardadas(self):
        flete = Flete.objects.create(
            cliente=self.cliente,
            chofer=self.chofer,
            fecha=date(2026, 5, 10),
            hora_inicio=time(9, 30),
            direccion_origen="Origen",
            direccion_destino="Destino",
            precio=Decimal("10000"),
            forma_de_pago="efectivo",
            estado="pendiente",
        )

        form = FleteForm(instance=flete)

        self.assertEqual(form["fecha"].value(), date(2026, 5, 10))
        self.assertEqual(form["hora_inicio"].value(), time(9, 30))

    def test_duplicado_usa_fecha_y_hora_actual_sin_copiar_horarios_reales(self):
        flete = Flete.objects.create(
            cliente=self.cliente,
            chofer=self.chofer,
            fecha=date(2026, 5, 10),
            hora_inicio=time(9, 30),
            direccion_origen="Origen",
            direccion_destino="Destino",
            precio=Decimal("10000"),
            forma_de_pago="cuenta_corriente",
            estado="pendiente",
        )
        flete.fecha_hora_en_curso = timezone.make_aware(timezone.datetime(2026, 5, 10, 10, 0))
        flete.fecha_hora_finalizado = timezone.make_aware(timezone.datetime(2026, 5, 10, 12, 0))
        flete.save(update_fields=["fecha_hora_en_curso", "fecha_hora_finalizado"])
        ahora_local = timezone.datetime(
            2026, 6, 24, 16, 5, 45, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")
        )

        with patch("core.views.timezone.localtime", return_value=ahora_local):
            response = self.client.get(reverse("duplicar_flete", args=[flete.id]))

        form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(form.initial["fecha"], date(2026, 6, 24))
        self.assertEqual(form.initial["hora_inicio"], time(16, 5))
        self.assertNotIn("hora_comienzo", form.initial)
        self.assertNotIn("hora_finalizacion", form.initial)


class ReservasRecurrentesTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre="Cliente recurrente",
            telefono="4444444444",
            direccion="Origen recurrente",
        )
        self.chofer = Chofer.objects.create(
            nombre="Chofer recurrente",
            telefono="5555555555",
            dni="66666666",
            patente="REC123",
        )

    def _datos_flete(self, **overrides):
        datos = {
            "cliente": self.cliente.id,
            "chofer": self.chofer.id,
            "fecha": "2026-07-01",
            "hora_inicio": "10:15",
            "direccion_origen": "Deposito",
            "direccion_destino": "Destino",
            "ayudantes": "1",
            "precio": "50000",
            "forma_de_pago": "cuenta_corriente",
            "estado": "pendiente",
            "tipo_repeticion": "no_repetir",
            "cantidad_repeticiones": "",
        }
        datos.update(overrides)
        return datos

    def test_crear_flete_sin_repeticion_crea_un_solo_flete(self):
        response = self.client.post(reverse("crear_flete"), self._datos_flete())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Flete.objects.count(), 1)
        flete = Flete.objects.get()
        self.assertEqual(flete.estado, "pendiente")
        self.assertEqual(flete.fecha, date(2026, 7, 1))
        self.assertEqual(flete.hora_inicio, time(10, 15))

    def test_crear_reserva_semanal_con_cuatro_repeticiones(self):
        response = self.client.post(
            reverse("crear_flete"),
            self._datos_flete(tipo_repeticion="semanal", cantidad_repeticiones="4"),
        )

        self.assertEqual(response.status_code, 302)
        fechas = list(Flete.objects.order_by("fecha").values_list("fecha", flat=True))
        self.assertEqual(
            fechas,
            [
                date(2026, 7, 1),
                date(2026, 7, 8),
                date(2026, 7, 15),
                date(2026, 7, 22),
            ],
        )
        self.assertEqual(Flete.objects.filter(estado="pendiente").count(), 4)
        self.assertFalse(Flete.objects.exclude(fecha_hora_en_curso=None).exists())
        self.assertFalse(Flete.objects.exclude(fecha_hora_finalizado=None).exists())
        self.assertFalse(Flete.objects.filter(cobro__isnull=False).exists())

    def test_crear_reserva_mensual_con_tres_repeticiones_ajusta_fin_de_mes(self):
        response = self.client.post(
            reverse("crear_flete"),
            self._datos_flete(
                fecha="2026-01-31",
                tipo_repeticion="mensual",
                cantidad_repeticiones="3",
            ),
        )

        self.assertEqual(response.status_code, 302)
        fechas = list(Flete.objects.order_by("fecha").values_list("fecha", flat=True))
        self.assertEqual(
            fechas,
            [
                date(2026, 1, 31),
                date(2026, 2, 28),
                date(2026, 3, 31),
            ],
        )

    def test_reserva_recurrente_fuerza_estado_pendiente_y_no_copia_datos_reales(self):
        response = self.client.post(
            reverse("crear_flete"),
            self._datos_flete(
                tipo_repeticion="semanal",
                cantidad_repeticiones="2",
                estado="finalizado",
            ),
        )

        self.assertEqual(response.status_code, 302)
        for flete in Flete.objects.all():
            self.assertEqual(flete.estado, "pendiente")
            self.assertEqual(flete.estado_cobro_cliente, "no_exigible")
            self.assertEqual(flete.estado_pago_chofer, "no_liquidable")
            self.assertIsNone(flete.fecha_hora_en_curso)
            self.assertIsNone(flete.fecha_hora_finalizado)
            self.assertIsNone(flete.fecha_pago_chofer)
            self.assertFalse(flete.pagado)

    def test_limite_maximo_de_repeticiones(self):
        form_semanal = FleteForm(
            data=self._datos_flete(tipo_repeticion="semanal", cantidad_repeticiones="53")
        )
        form_mensual = FleteForm(
            data=self._datos_flete(tipo_repeticion="mensual", cantidad_repeticiones="25")
        )

        self.assertFalse(form_semanal.is_valid())
        self.assertIn("cantidad_repeticiones", form_semanal.errors)
        self.assertFalse(form_mensual.is_valid())
        self.assertIn("cantidad_repeticiones", form_mensual.errors)

    def _crear_flete(self, fecha, hora=time(10, 15), estado="pendiente"):
        return Flete.objects.create(
            cliente=self.cliente,
            chofer=self.chofer,
            fecha=fecha,
            hora_inicio=hora,
            direccion_origen="Deposito",
            direccion_destino="Destino",
            ayudantes=1,
            precio=Decimal("50000"),
            forma_de_pago="cuenta_corriente",
            estado=estado,
        )

    def test_home_muestra_hoy_y_reservas_solo_de_proximos_siete_dias(self):
        hoy = timezone.localdate()
        flete_hoy = self._crear_flete(hoy, time(9, 0))
        reserva_manana = self._crear_flete(hoy + timezone.timedelta(days=1), time(10, 0))
        reserva_dia_siete = self._crear_flete(hoy + timezone.timedelta(days=7), time(11, 0))
        reserva_fuera_de_rango = self._crear_flete(hoy + timezone.timedelta(days=8), time(12, 0))

        response = self.client.get(reverse("panel_inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["fletes_hoy"]), [flete_hoy])
        self.assertEqual(
            list(response.context["reservas_futuras"]),
            [reserva_manana, reserva_dia_siete],
        )
        self.assertNotIn(reserva_fuera_de_rango, response.context["reservas_futuras"])

    def test_reserva_fuera_de_siete_dias_sigue_en_listado_general(self):
        reserva_fuera_de_rango = self._crear_flete(timezone.localdate() + timezone.timedelta(days=8))

        response = self.client.get(reverse("lista_fletes"), {"estado": "pendiente"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(reserva_fuera_de_rango, response.context["fletes"])

    def test_home_sin_reservas_en_proximos_siete_dias_muestra_mensaje(self):
        self._crear_flete(timezone.localdate() + timezone.timedelta(days=8))

        response = self.client.get(reverse("panel_inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay reservas cargadas para los proximos 7 dias.")
        self.assertEqual(len(response.context["reservas_futuras"]), 0)

    def test_home_elimina_cards_duplicadas_y_conserva_operacion_diaria(self):
        response = self.client.get(reverse("panel_inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel operativo diario")
        self.assertContains(response, "Fletes de hoy")
        self.assertContains(response, "Reservas / proximos fletes")
        self.assertContains(response, '<a href="/fletes/nuevo/" class="panel-hero-accion">Nuevo flete</a>', html=True)
        self.assertContains(response, '<a href="/" class="secundario">Panel</a>', html=True)
        self.assertContains(response, '<a href="/fletes/" class="secundario">Fletes</a>', html=True)
        self.assertNotContains(response, "atajos-grid")
        self.assertNotContains(response, "atajo-panel")
        self.assertNotContains(response, "Administrar clientes")
        self.assertNotContains(response, "Administrar choferes")
        self.assertNotContains(response, "Seguimiento de cobros")
        self.assertNotContains(response, "Pagos pendientes a choferes")
        self.assertNotContains(response, "Fletes finalizados y cobro")

    def test_editar_flete_normal_sigue_funcionando(self):
        flete = Flete.objects.create(
            cliente=self.cliente,
            chofer=self.chofer,
            fecha=date(2026, 7, 1),
            hora_inicio=time(10, 15),
            direccion_origen="Deposito",
            direccion_destino="Destino",
            ayudantes=1,
            precio=Decimal("50000"),
            forma_de_pago="cuenta_corriente",
            estado="pendiente",
        )

        response = self.client.post(
            reverse("editar_flete", args=[flete.id]),
            self._datos_flete(
                fecha="2026-07-02",
                hora_inicio="11:45",
                direccion_destino="Destino editado",
            ),
        )

        flete.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(flete.fecha, date(2026, 7, 2))
        self.assertEqual(flete.hora_inicio, time(11, 45))
        self.assertEqual(flete.direccion_destino, "Destino editado")

    def test_duplicar_flete_guarda_un_flete_nuevo(self):
        flete = Flete.objects.create(
            cliente=self.cliente,
            chofer=self.chofer,
            fecha=date(2026, 7, 1),
            hora_inicio=time(10, 15),
            direccion_origen="Deposito",
            direccion_destino="Destino",
            ayudantes=1,
            precio=Decimal("50000"),
            forma_de_pago="cuenta_corriente",
            estado="pendiente",
        )

        response = self.client.post(
            reverse("duplicar_flete", args=[flete.id]),
            self._datos_flete(fecha="2026-07-08", hora_inicio="12:00"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Flete.objects.count(), 2)
        self.assertTrue(Flete.objects.filter(fecha=date(2026, 7, 8), hora_inicio=time(12, 0)).exists())

    def test_estado_pendiente_de_flete_se_muestra_como_reserva(self):
        self._crear_flete(timezone.localdate(), estado="pendiente")

        response = self.client.get(reverse("lista_fletes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reserva")
        self.assertContains(response, "Reservas")
        self.assertNotContains(response, ">Pendiente</span>", html=False)

    def test_filtro_reservas_sigue_filtrando_estado_interno_pendiente(self):
        reserva = self._crear_flete(timezone.localdate(), estado="pendiente")
        en_curso = self._crear_flete(timezone.localdate(), time(11, 0), estado="en_curso")

        response = self.client.get(reverse("lista_fletes"), {"filtro": "pendientes"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(reserva, response.context["fletes"])
        self.assertNotIn(en_curso, response.context["fletes"])
        self.assertContains(response, "Reservas")

    def test_formulario_flete_muestra_reserva_sin_cambiar_valor_interno(self):
        response = self.client.get(reverse("crear_flete"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="pendiente" selected>Reserva</option>', html=True)

    def test_estados_no_pendientes_conservan_su_etiqueta(self):
        self._crear_flete(timezone.localdate(), estado="en_curso")
        self._crear_flete(timezone.localdate(), time(11, 0), estado="finalizado")
        self._crear_flete(timezone.localdate(), time(12, 0), estado="cancelado")

        response = self.client.get(reverse("lista_fletes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En curso")
        self.assertContains(response, "Finalizado")
        self.assertContains(response, "Cancelado")

    def test_pendiente_de_cobro_sigue_diciendo_pendiente(self):
        flete = self._crear_flete(timezone.localdate(), estado="finalizado")
        flete.estado_cobro_cliente = "pendiente"
        flete.save(update_fields=["estado_cobro_cliente"])

        response = self.client.get(reverse("facturacion"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pendiente de cobro")
        self.assertContains(response, "Pendiente")
        self.assertNotContains(response, "Reserva de cobro")

    def test_acciones_de_reserva_muestran_solo_en_curso(self):
        self._crear_flete(timezone.localdate(), estado="pendiente")

        response = self.client.get(reverse("lista_fletes"), {"estado": "pendiente"})

        self.assertContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a reserva</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a en curso</button>', html=True)
        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")

    def test_acciones_de_en_curso_muestran_finalizar_y_volver_a_reserva(self):
        self._crear_flete(timezone.localdate(), estado="en_curso")

        response = self.client.get(reverse("lista_fletes"), {"estado": "en_curso"})

        self.assertContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertContains(response, '<button type="submit">Volver a reserva</button>', html=True)
        self.assertContains(response, "Se limpiaran los horarios reales cargados.")
        self.assertNotContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a en curso</button>', html=True)
        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")

    def test_acciones_de_finalizado_muestran_solo_volver_a_en_curso(self):
        self._crear_flete(timezone.localdate(), estado="finalizado")

        response = self.client.get(reverse("lista_fletes"))

        self.assertContains(response, '<button type="submit">Volver a en curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertNotContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a reserva</button>', html=True)
        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")

    def test_volver_de_en_curso_a_reserva_limpia_horarios_y_muestra_reserva(self):
        flete = self._crear_flete(timezone.localdate(), estado="en_curso")
        self.assertIsNotNone(flete.fecha_hora_en_curso)

        response = self.client.post(reverse("cambiar_estado_flete", args=[flete.id, "pendiente"]))

        flete.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(flete.estado, "pendiente")
        self.assertIsNone(flete.fecha_hora_en_curso)
        self.assertIsNone(flete.fecha_hora_finalizado)
        self.assertIsNone(flete.duracion)

        response = self.client.get(reverse("lista_fletes"))
        self.assertContains(response, "Reserva")

    def test_home_reserva_muestra_editar_duplicar_y_en_curso(self):
        self._crear_flete(timezone.localdate(), estado="pendiente")

        response = self.client.get(reverse("panel_inicio"))

        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")
        self.assertContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a reserva</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a en curso</button>', html=True)

    def test_home_en_curso_muestra_editar_duplicar_finalizar_y_volver_a_reserva(self):
        self._crear_flete(timezone.localdate(), estado="en_curso")

        response = self.client.get(reverse("panel_inicio"))

        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")
        self.assertContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertContains(response, '<button type="submit">Volver a reserva</button>', html=True)
        self.assertNotContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a en curso</button>', html=True)

    def test_home_finalizado_muestra_editar_duplicar_y_volver_a_en_curso(self):
        self._crear_flete(timezone.localdate(), estado="finalizado")

        response = self.client.get(reverse("panel_inicio"))

        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")
        self.assertContains(response, '<button type="submit">Volver a en curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a reserva</button>', html=True)

    def test_home_cancelado_muestra_solo_editar_y_duplicar(self):
        self._crear_flete(timezone.localdate(), estado="cancelado")

        response = self.client.get(reverse("panel_inicio"))

        self.assertContains(response, "Editar")
        self.assertContains(response, "Duplicar")
        self.assertNotContains(response, '<button type="submit">En curso</button>', html=True)
        self.assertNotContains(response, '<button type="submit" class="btn-exito">Finalizar</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a reserva</button>', html=True)
        self.assertNotContains(response, '<button type="submit">Volver a en curso</button>', html=True)

    def test_accion_home_reserva_a_en_curso_guarda_inicio_y_vuelve_al_panel(self):
        flete = self._crear_flete(timezone.localdate(), estado="pendiente")

        response = self.client.post(
            reverse("cambiar_estado_flete", args=[flete.id, "en_curso"]),
            {"next": reverse("panel_inicio")},
        )

        flete.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("panel_inicio"))
        self.assertEqual(flete.estado, "en_curso")
        self.assertIsNotNone(flete.fecha_hora_en_curso)
        self.assertIsNone(flete.fecha_hora_finalizado)

    def test_accion_home_en_curso_a_finalizado_guarda_final_y_duracion(self):
        flete = self._crear_flete(timezone.localdate(), estado="en_curso")

        response = self.client.post(
            reverse("cambiar_estado_flete", args=[flete.id, "finalizado"]),
            {"next": reverse("panel_inicio")},
        )

        flete.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("panel_inicio"))
        self.assertEqual(flete.estado, "finalizado")
        self.assertIsNotNone(flete.fecha_hora_en_curso)
        self.assertIsNotNone(flete.fecha_hora_finalizado)
        self.assertIsNotNone(flete.duracion)

    def test_accion_home_en_curso_a_reserva_limpia_horarios(self):
        flete = self._crear_flete(timezone.localdate(), estado="en_curso")

        response = self.client.post(
            reverse("cambiar_estado_flete", args=[flete.id, "pendiente"]),
            {"next": reverse("panel_inicio")},
        )

        flete.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("panel_inicio"))
        self.assertEqual(flete.estado, "pendiente")
        self.assertIsNone(flete.fecha_hora_en_curso)
        self.assertIsNone(flete.fecha_hora_finalizado)
        self.assertIsNone(flete.duracion)

    def test_accion_home_finalizado_a_en_curso_limpia_finalizacion_y_cobro(self):
        flete = self._crear_flete(timezone.localdate(), estado="finalizado")
        self.assertIsNotNone(flete.fecha_hora_finalizado)
        self.assertEqual(flete.estado_cobro_cliente, "pendiente")

        response = self.client.post(
            reverse("cambiar_estado_flete", args=[flete.id, "en_curso"]),
            {"next": reverse("panel_inicio")},
        )

        flete.refresh_from_db()
        flete.cobro.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("panel_inicio"))
        self.assertEqual(flete.estado, "en_curso")
        self.assertIsNotNone(flete.fecha_hora_en_curso)
        self.assertIsNone(flete.fecha_hora_finalizado)
        self.assertIsNone(flete.duracion)
        self.assertEqual(flete.estado_cobro_cliente, "no_exigible")
        self.assertEqual(flete.cobro.estado, "pendiente")
        self.assertIsNone(flete.cobro.fecha_pago)

    def test_listado_fletes_sin_filtros_muestra_historico_finalizado_hasta_hoy(self):
        hoy = timezone.localdate()
        finalizado_pasado = self._crear_flete(hoy - timezone.timedelta(days=2), estado="finalizado")
        finalizado_hoy = self._crear_flete(hoy, time(11, 0), estado="finalizado")
        self._crear_flete(hoy + timezone.timedelta(days=1), time(12, 0), estado="finalizado")
        self._crear_flete(hoy, time(13, 0), estado="pendiente")
        self._crear_flete(hoy, time(14, 0), estado="en_curso")

        response = self.client.get(reverse("lista_fletes"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["fletes"]), [finalizado_hoy, finalizado_pasado])
        self.assertTrue(response.context["filtros"]["historico_default"])
        self.assertContains(response, "Mostrando historico: fletes finalizados hasta hoy.")

    def test_listado_fletes_filtra_por_desde_y_hasta(self):
        flete_1 = self._crear_flete(date(2026, 6, 10), estado="finalizado")
        flete_2 = self._crear_flete(date(2026, 6, 15), time(11, 0), estado="finalizado")
        self._crear_flete(date(2026, 6, 20), time(12, 0), estado="finalizado")

        response = self.client.get(
            reverse("lista_fletes"),
            {"fecha_desde": "2026-06-10", "fecha_hasta": "2026-06-15"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["fletes"]), [flete_2, flete_1])
        self.assertFalse(response.context["filtros"]["historico_default"])

    def test_listado_fletes_filtra_solo_desde(self):
        self._crear_flete(date(2026, 6, 10), estado="finalizado")
        flete_2 = self._crear_flete(date(2026, 6, 15), time(11, 0), estado="finalizado")
        flete_3 = self._crear_flete(date(2026, 6, 20), time(12, 0), estado="finalizado")

        response = self.client.get(reverse("lista_fletes"), {"fecha_desde": "2026-06-15"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["fletes"]), [flete_3, flete_2])

    def test_listado_fletes_filtra_solo_hasta(self):
        flete_1 = self._crear_flete(date(2026, 6, 10), estado="finalizado")
        flete_2 = self._crear_flete(date(2026, 6, 15), time(11, 0), estado="finalizado")
        self._crear_flete(date(2026, 6, 20), time(12, 0), estado="finalizado")

        response = self.client.get(reverse("lista_fletes"), {"fecha_hasta": "2026-06-15"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["fletes"]), [flete_2, flete_1])

    def test_listado_fletes_respeta_estado_reserva_y_en_curso(self):
        hoy = timezone.localdate()
        reserva = self._crear_flete(hoy + timezone.timedelta(days=1), estado="pendiente")
        en_curso = self._crear_flete(hoy, time(11, 0), estado="en_curso")
        self._crear_flete(hoy, time(12, 0), estado="finalizado")

        response_reserva = self.client.get(reverse("lista_fletes"), {"estado": "pendiente"})
        response_en_curso = self.client.get(reverse("lista_fletes"), {"estado": "en_curso"})

        self.assertEqual(list(response_reserva.context["fletes"]), [reserva])
        self.assertEqual(list(response_en_curso.context["fletes"]), [en_curso])
        self.assertFalse(response_reserva.context["filtros"]["historico_default"])
        self.assertFalse(response_en_curso.context["filtros"]["historico_default"])

    def test_limpiar_fletes_vuelve_al_historico_default(self):
        response = self.client.get(reverse("lista_fletes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<a href="/fletes/" class="btn-secundario">Limpiar</a>', html=True)
        self.assertTrue(response.context["filtros"]["historico_default"])

    def test_clientes_busca_por_nombre_telefono_y_direccion(self):
        cliente_nombre = self.cliente
        cliente_nombre.nombre = "Cliente Norte"
        cliente_nombre.telefono = "1111111111"
        cliente_nombre.direccion = "Calle A"
        cliente_nombre.save()
        cliente_telefono = Cliente.objects.create(nombre="Cliente Sur", telefono="22223333", direccion="Calle B")
        cliente_direccion = Cliente.objects.create(nombre="Cliente Oeste", telefono="33334444", direccion="Ruta 8 km 44")

        response_nombre = self.client.get(reverse("lista_clientes"), {"buscar": "norte"})
        response_telefono = self.client.get(reverse("lista_clientes"), {"buscar": "2222"})
        response_direccion = self.client.get(reverse("lista_clientes"), {"buscar": "ruta 8"})

        self.assertEqual(list(response_nombre.context["clientes"]), [cliente_nombre])
        self.assertEqual(list(response_telefono.context["clientes"]), [cliente_telefono])
        self.assertEqual(list(response_direccion.context["clientes"]), [cliente_direccion])
        self.assertContains(response_direccion, 'value="ruta 8"')

    def test_clientes_busqueda_sin_resultados_y_limpiar(self):
        response = self.client.get(reverse("lista_clientes"), {"buscar": "no-existe"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["clientes"]), [])
        self.assertContains(response, "No se encontraron clientes para la busqueda aplicada.")
        self.assertContains(response, '<a href="/clientes/" class="btn-secundario">Limpiar</a>', html=True)

    def test_nuevo_chofer_tiene_porcentaje_estandar_80(self):
        chofer = Chofer.objects.create(
            nombre="Chofer 80",
            telefono="7777777777",
            dni="77777777",
            patente="STD080",
        )

        self.assertEqual(chofer.porcentaje_liquidacion, 80)

    def test_editar_chofer_permanece_modificable(self):
        response = self.client.post(
            reverse("editar_chofer", args=[self.chofer.id]),
            {
                "nombre": self.chofer.nombre,
                "telefono": self.chofer.telefono,
                "dni": self.chofer.dni,
                "registro": "REG",
                "direccion": "Base",
                "estado": "activo",
                "tipo_liquidacion": "semanal",
                "porcentaje_liquidacion": "75",
                "vehiculo": "Camion",
                "patente": self.chofer.patente,
                "seguro": "Seguro",
            },
        )

        self.chofer.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.chofer.porcentaje_liquidacion, 75)

    def test_porcentaje_80_no_figura_como_excepcion_y_porcentaje_distinto_si(self):
        Chofer.objects.create(
            nombre="Chofer especial",
            telefono="8888888888",
            dni="88888888",
            patente="ESP075",
            porcentaje_liquidacion=75,
        )

        response = self.client.get(reverse("lista_choferes"))

        self.assertContains(response, "Estandar 80%")
        self.assertContains(response, '<span class="estado">80%</span>', html=True)
        self.assertContains(response, "Excepcion: 75%")

    def test_filtros_estandar_y_excepcion_usan_80(self):
        especial = Chofer.objects.create(
            nombre="Chofer especial",
            telefono="9999999999",
            dni="99999999",
            patente="ESP070",
            porcentaje_liquidacion=70,
        )

        response_estandar = self.client.get(reverse("lista_choferes"), {"porcentaje": "estandar"})
        response_excepcion = self.client.get(reverse("lista_choferes"), {"porcentaje": "excepcion"})

        self.assertIn(self.chofer, response_estandar.context["choferes"])
        self.assertNotIn(especial, response_estandar.context["choferes"])
        self.assertIn(especial, response_excepcion.context["choferes"])
        self.assertNotIn(self.chofer, response_excepcion.context["choferes"])

    def test_importe_chofer_y_reportes_usan_porcentaje_80(self):
        flete = self._crear_flete(timezone.localdate(), estado="finalizado")

        response = self.client.get(reverse("reportes"))

        self.assertEqual(flete.importe_chofer, Decimal("40000.00"))
        self.assertEqual(response.context["total_a_pagar_choferes"], Decimal("40000.00"))

    def test_flete_existente_recalcula_importe_con_porcentaje_actual_del_chofer(self):
        flete = self._crear_flete(timezone.localdate(), estado="finalizado")
        self.assertEqual(flete.importe_chofer, Decimal("40000.00"))

        self.chofer.porcentaje_liquidacion = 70
        self.chofer.save(update_fields=["porcentaje_liquidacion"])
        flete.refresh_from_db()

        self.assertEqual(flete.importe_chofer, Decimal("35000.00"))
