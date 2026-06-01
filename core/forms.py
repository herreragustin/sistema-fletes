from django import forms
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
        self.fields["direccion_origen"].error_messages["required"] = "Debe ingresar un origen"
        self.fields["direccion_destino"].error_messages["required"] = "Debe ingresar un destino"
        self.fields["precio"].error_messages["required"] = "Debe ingresar un precio"

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

        if estado == "finalizado":
            if not origen:
                self.add_error("direccion_origen", "No se puede finalizar un flete sin origen")
            if not destino:
                self.add_error("direccion_destino", "No se puede finalizar un flete sin destino")
            if precio is None or precio <= 0:
                self.add_error("precio", "No se puede finalizar un flete con precio menor o igual a cero")

        return cleaned_data
