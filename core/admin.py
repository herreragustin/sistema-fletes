from django import forms
from django.contrib import admin
from .models import Cliente, Chofer, Flete, Cobro, Factura, Viaje

class FleteAdminForm(forms.ModelForm):
    class Meta:
        model = Flete
        exclude = ("observaciones", "observaciones_pago_chofer")
        widgets = {
            'fecha': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
        }

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "telefono", "direccion", "activo", "codigo_legacy", "fecha_creacion")
    search_fields = ("nombre", "telefono", "direccion", "codigo_legacy")
    list_filter = ("activo",)


@admin.register(Chofer)
class ChoferAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "telefono", "dni", "estado", "tipo_liquidacion", "porcentaje_liquidacion", "vehiculo", "patente", "codigo_legacy")
    search_fields = ("nombre", "telefono", "dni", "patente", "codigo_legacy")
    list_filter = ("estado", "tipo_liquidacion")


@admin.register(Flete)
class FleteAdmin(admin.ModelAdmin):
    form = FleteAdminForm  
    list_display = (
        "id",
        "cliente",
        "chofer",
        "fecha",
        "hora_inicio",
        "direccion_origen",
        "direccion_destino",
        "precio",
        "estado",
    )
    search_fields = (
        "cliente__nombre",
        "chofer__nombre",
        "direccion_origen",
        "direccion_destino",
    )
    list_filter = ("estado", "fecha", "chofer", "cliente")
    autocomplete_fields = ("cliente", "chofer")


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "flete",
        "get_cliente",
        "get_chofer",
        "monto",
        "metodo_pago",
        "estado",
        "fecha_pago",
    )
    search_fields = (
        "flete__id",
        "flete__cliente__nombre",
        "flete__chofer__nombre",
    )
    list_filter = ("estado", "metodo_pago", "flete__cliente", "flete__chofer")

    @admin.display(description="Cliente")
    def get_cliente(self, obj):
        return obj.flete.cliente

    @admin.display(description="Chofer")
    def get_chofer(self, obj):
        return obj.flete.chofer


@admin.register(Viaje)
class ViajeAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo_legacy", "fecha", "cliente", "chofer", "origen", "destino", "importe", "estado")
    search_fields = ("codigo_legacy", "cliente__nombre", "chofer__nombre", "origen", "destino")
    list_filter = ("estado", "fecha", "cliente", "chofer")
    autocomplete_fields = ("cliente", "chofer")
    readonly_fields = ("datos_legacy", "fecha_importacion")


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ("id", "numero", "fecha", "cliente", "viaje", "importe_total", "estado", "codigo_legacy")
    search_fields = ("numero", "codigo_legacy", "cliente__nombre", "viaje__codigo_legacy")
    list_filter = ("estado", "fecha", "cliente")
    autocomplete_fields = ("cliente", "viaje")
    readonly_fields = ("datos_legacy", "fecha_importacion")
