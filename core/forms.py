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
        self.fields["direccion_origen"].widget.attrs["list"] = "direcciones_cliente"
        self.fields["direccion_destino"].widget.attrs["list"] = "direcciones_cliente"

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
