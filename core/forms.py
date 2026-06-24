from datetime import datetime

from django import forms
from django.utils import timezone
from django.db.models import Q

from .models import Cliente, Chofer, Flete


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "telefono", "direccion", "activo"]

    def clean_telefono(self):
        return self.cleaned_data["telefono"] or None


class ChoferForm(forms.ModelForm):
    class Meta:
        model = Chofer
        fields = [
            "nombre",
            "telefono",
            "dni",
            "registro",
            "direccion",
            "estado",
            "tipo_liquidacion",
            "porcentaje_liquidacion",
            "vehiculo",
            "patente",
            "seguro",
        ]
        labels = {
            "porcentaje_liquidacion": "Porcentaje de liquidacion",
        }

    def clean_telefono(self):
        return self.cleaned_data["telefono"] or None

    def clean_dni(self):
        return self.cleaned_data["dni"] or None

    def clean_patente(self):
        return self.cleaned_data["patente"] or None


class FleteForm(forms.ModelForm):
    TIPO_REPETICION = [
        ("no_repetir", "No repetir"),
        ("semanal", "Semanal"),
        ("mensual", "Mensual"),
    ]

    hora_comienzo = forms.TimeField(
        required=False,
        label="Hora de comienzo",
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
    )
    hora_finalizacion = forms.TimeField(
        required=False,
        label="Hora de finalizacion",
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
    )
    tipo_repeticion = forms.ChoiceField(
        choices=TIPO_REPETICION,
        required=False,
        initial="no_repetir",
        label="Tipo de repeticion",
    )
    cantidad_repeticiones = forms.IntegerField(
        required=False,
        min_value=1,
        label="Cantidad de repeticiones",
        widget=forms.NumberInput(attrs={"min": "1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cliente_qs = Cliente.objects.filter(activo=True)
        chofer_qs = Chofer.objects.filter(estado="activo")

        if self.instance.pk:
            cliente_qs = Cliente.objects.filter(Q(activo=True) | Q(pk=self.instance.cliente_id))
            chofer_qs = Chofer.objects.filter(Q(estado="activo") | Q(pk=self.instance.chofer_id))

        self.fields["cliente"].queryset = cliente_qs.order_by("nombre")
        self.fields["chofer"].queryset = chofer_qs.order_by("nombre")
        self.fields["cliente"].error_messages["required"] = "Debe seleccionar un cliente"
        self.fields["chofer"].error_messages["required"] = "Debe seleccionar un chofer"
        self.fields["fecha"].error_messages["required"] = "Debe ingresar una fecha"
        self.fields["hora_inicio"].label = "Hora programada"
        self.fields["estado"].choices = [
            ("pendiente", "Reserva") if value == "pendiente" else (value, label)
            for value, label in self.fields["estado"].choices
        ]
        self.fields["direccion_origen"].error_messages["required"] = "Debe ingresar un origen"
        self.fields["direccion_destino"].error_messages["required"] = "Debe ingresar un destino"
        self.fields["precio"].error_messages["required"] = "Debe ingresar un precio"

        if not self.is_bound and not self.instance.pk:
            ahora_local = timezone.localtime()
            self.initial.setdefault("fecha", ahora_local.date())
            self.initial.setdefault("hora_inicio", ahora_local.time().replace(second=0, microsecond=0))

        if self.instance.pk:
            if self.instance.fecha_hora_en_curso:
                self.initial["hora_comienzo"] = timezone.localtime(self.instance.fecha_hora_en_curso).strftime("%H:%M")
            if self.instance.fecha_hora_finalizado:
                self.initial["hora_finalizacion"] = timezone.localtime(self.instance.fecha_hora_finalizado).strftime("%H:%M")

    class Meta:
        model = Flete
        fields = [
            "cliente",
            "chofer",
            "fecha",
            "hora_inicio",
            "direccion_origen",
            "direccion_destino",
            "ayudantes",
            "precio",
            "forma_de_pago",
            "estado",
        ]
        widgets = {
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        cliente = cleaned_data.get("cliente")
        chofer = cleaned_data.get("chofer")
        fecha = cleaned_data.get("fecha")
        origen = (cleaned_data.get("direccion_origen") or "").strip()
        destino = (cleaned_data.get("direccion_destino") or "").strip()
        precio = cleaned_data.get("precio")
        estado = cleaned_data.get("estado")
        hora_comienzo = cleaned_data.get("hora_comienzo")
        hora_finalizacion = cleaned_data.get("hora_finalizacion")
        tipo_repeticion = cleaned_data.get("tipo_repeticion") or "no_repetir"
        cantidad_repeticiones = cleaned_data.get("cantidad_repeticiones")
        estado_anterior = self.instance.estado if self.instance and self.instance.pk else None

        if tipo_repeticion != "no_repetir":
            cleaned_data["estado"] = "pendiente"
            estado = "pendiente"

        if "cliente" not in self.errors and not cliente:
            self.add_error("cliente", "Debe seleccionar un cliente")

        if "fecha" not in self.errors and not fecha:
            self.add_error("fecha", "Debe ingresar una fecha")

        if "direccion_origen" not in self.errors and not origen:
            self.add_error("direccion_origen", "Debe ingresar un origen")

        if "direccion_destino" not in self.errors and not destino:
            self.add_error("direccion_destino", "Debe ingresar un destino")

        if "precio" not in self.errors and precio is None:
            self.add_error("precio", "Debe ingresar un precio")
        elif "precio" not in self.errors and precio <= 0:
            self.add_error("precio", "El precio debe ser mayor a cero")

        if "chofer" not in self.errors and estado in {"en_curso", "finalizado"} and not chofer:
            mensaje = "No se puede iniciar un flete sin chofer asignado" if estado == "en_curso" else "No se puede finalizar un flete sin chofer asignado"
            self.add_error("chofer", mensaje)

        if tipo_repeticion != "no_repetir":
            if cantidad_repeticiones is None:
                self.add_error("cantidad_repeticiones", "Debe ingresar la cantidad de repeticiones")
            elif cantidad_repeticiones <= 0:
                self.add_error("cantidad_repeticiones", "La cantidad de repeticiones debe ser mayor a cero")
            elif tipo_repeticion == "semanal" and cantidad_repeticiones > 52:
                self.add_error("cantidad_repeticiones", "Para repeticion semanal el maximo es 52")
            elif tipo_repeticion == "mensual" and cantidad_repeticiones > 24:
                self.add_error("cantidad_repeticiones", "Para repeticion mensual el maximo es 24")

        if estado == "finalizado":
            if not origen:
                self.add_error("direccion_origen", "No se puede finalizar un flete sin origen")
            if not destino:
                self.add_error("direccion_destino", "No se puede finalizar un flete sin destino")
            if precio is None or precio <= 0:
                self.add_error("precio", "No se puede finalizar un flete con precio menor o igual a cero")

            requiere_horarios_manuales = (
                estado_anterior != "finalizado"
                and not self.instance.fecha_hora_en_curso
                and not self.instance.fecha_hora_finalizado
            )

            if hora_comienzo and not hora_finalizacion:
                self.add_error("hora_finalizacion", "Debe ingresar la hora de finalizacion")
            if hora_finalizacion and not hora_comienzo:
                self.add_error("hora_comienzo", "Debe ingresar la hora de comienzo")

            if requiere_horarios_manuales and not hora_comienzo:
                self.add_error(
                    "hora_comienzo",
                    "Debe ingresar la hora de comienzo para cargar un flete ya finalizado",
                )
            if requiere_horarios_manuales and not hora_finalizacion:
                self.add_error(
                    "hora_finalizacion",
                    "Debe ingresar la hora de finalizacion para cargar un flete ya finalizado",
                )

            if fecha and hora_comienzo and hora_finalizacion:
                inicio_dt = timezone.make_aware(datetime.combine(fecha, hora_comienzo))
                fin_dt = timezone.make_aware(datetime.combine(fecha, hora_finalizacion))
                if inicio_dt >= fin_dt:
                    self.add_error("hora_finalizacion", "La hora de finalizacion debe ser posterior a la hora de comienzo")
                else:
                    cleaned_data["fecha_hora_en_curso_manual"] = inicio_dt
                    cleaned_data["fecha_hora_finalizado_manual"] = fin_dt

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        fecha_hora_en_curso_manual = self.cleaned_data.get("fecha_hora_en_curso_manual")
        fecha_hora_finalizado_manual = self.cleaned_data.get("fecha_hora_finalizado_manual")

        if fecha_hora_en_curso_manual and fecha_hora_finalizado_manual:
            instance.fecha_hora_en_curso = fecha_hora_en_curso_manual
            instance.fecha_hora_finalizado = fecha_hora_finalizado_manual
            instance._usar_horarios_manuales = True

        if commit:
            instance.save()
            self.save_m2m()

        return instance
