from django.db import models


class LegacyBaseModel(models.Model):
    codigo_legacy = models.CharField(max_length=80, unique=True)
    origen_legacy = models.CharField(max_length=40, blank=True)
    datos_legacy = models.JSONField(default=dict, blank=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class ClienteHistorico(LegacyBaseModel):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=40, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Cliente historico"
        verbose_name_plural = "Clientes historicos"
        ordering = ["nombre", "codigo_legacy"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo_legacy})"


class ChoferHistorico(LegacyBaseModel):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=40, blank=True)
    dni = models.CharField(max_length=40, blank=True)
    registro = models.CharField(max_length=80, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=30, blank=True)
    vehiculo = models.CharField(max_length=120, blank=True)
    patente = models.CharField(max_length=40, blank=True)
    seguro = models.CharField(max_length=120, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Chofer historico"
        verbose_name_plural = "Choferes historicos"
        ordering = ["nombre", "codigo_legacy"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo_legacy})"


class ViajeHistorico(LegacyBaseModel):
    ESTADO_VIAJE = [
        ("reserva", "Reserva"),
        ("pendiente", "Pendiente"),
        ("en_curso", "En curso"),
        ("finalizado", "Finalizado"),
        ("cancelado", "Cancelado"),
        ("sin_estado", "Sin estado"),
    ]

    cliente = models.ForeignKey(
        ClienteHistorico,
        on_delete=models.SET_NULL,
        related_name="viajes_historicos",
        blank=True,
        null=True,
    )
    chofer = models.ForeignKey(
        ChoferHistorico,
        on_delete=models.SET_NULL,
        related_name="viajes_historicos",
        blank=True,
        null=True,
    )
    cliente_codigo_legacy = models.CharField(max_length=80, blank=True)
    chofer_codigo_legacy = models.CharField(max_length=80, blank=True)
    fecha = models.DateField(blank=True, null=True)
    hora = models.TimeField(blank=True, null=True)
    origen = models.CharField(max_length=255, blank=True)
    destino = models.CharField(max_length=255, blank=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_VIAJE, default="sin_estado")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Viaje historico"
        verbose_name_plural = "Viajes historicos"
        ordering = ["-fecha", "-hora", "-codigo_legacy"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["codigo_legacy"]),
        ]

    def __str__(self):
        return f"Viaje {self.codigo_legacy}"


class ReservaHistorica(LegacyBaseModel):
    ESTADO_RESERVA = [
        ("reserva", "Reserva"),
        ("pendiente", "Pendiente"),
        ("en_curso", "En curso"),
        ("finalizado", "Finalizado"),
        ("cancelado", "Cancelado"),
        ("sin_estado", "Sin estado"),
    ]

    cliente = models.ForeignKey(
        ClienteHistorico,
        on_delete=models.SET_NULL,
        related_name="reservas_historicas",
        blank=True,
        null=True,
    )
    chofer = models.ForeignKey(
        ChoferHistorico,
        on_delete=models.SET_NULL,
        related_name="reservas_historicas",
        blank=True,
        null=True,
    )
    cliente_codigo_legacy = models.CharField(max_length=80, blank=True)
    chofer_codigo_legacy = models.CharField(max_length=80, blank=True)
    fecha = models.DateField(blank=True, null=True)
    hora = models.TimeField(blank=True, null=True)
    origen = models.CharField(max_length=255, blank=True)
    destino = models.CharField(max_length=255, blank=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_RESERVA, default="reserva")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Reserva historica"
        verbose_name_plural = "Reservas historicas"
        ordering = ["-fecha", "-hora", "-codigo_legacy"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["codigo_legacy"]),
        ]

    def __str__(self):
        return f"Reserva {self.codigo_legacy}"
