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
