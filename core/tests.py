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

        response = self.client.get(reverse("lista_fletes"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(reserva_fuera_de_rango, response.context["fletes"])

    def test_home_sin_reservas_en_proximos_siete_dias_muestra_mensaje(self):
        self._crear_flete(timezone.localdate() + timezone.timedelta(days=8))

        response = self.client.get(reverse("panel_inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay reservas cargadas para los proximos 7 dias.")
        self.assertEqual(len(response.context["reservas_futuras"]), 0)

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
