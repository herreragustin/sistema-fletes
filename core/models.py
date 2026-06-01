from datetime import timedelta
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    codigo_legacy = models.CharField(max_length=50, blank=True, null=True, unique=True)
    origen_legacy = models.CharField(max_length=30, blank=True)
    datos_legacy = models.JSONField(default=dict, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} - {self.telefono}"


class Chofer(models.Model):
    ESTADO_CHOFER = [
        ("activo", "Activo"),
        ("inactivo", "Inactivo"),
    ]
    TIPO_LIQUIDACION = [
        ("semanal", "Semanal"),
        ("quincenal", "Quincenal"),
        ("mensual", "Mensual"),
    ]

    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True, blank=True, null=True)
    dni = models.CharField(max_length=20, unique=True, blank=True, null=True)
    registro = models.CharField(max_length=50, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOFER, default="activo")
    vehiculo = models.CharField(max_length=100, blank=True)
    patente = models.CharField(max_length=20, unique=True, blank=True, null=True)
    seguro = models.CharField(max_length=100, blank=True)
    tipo_liquidacion = models.CharField(
        max_length=20,
        choices=TIPO_LIQUIDACION,
        default="semanal",
    )
    porcentaje_liquidacion = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Porcentaje de liquidacion",
    )
    codigo_legacy = models.CharField(max_length=50, blank=True, null=True, unique=True)
    origen_legacy = models.CharField(max_length=30, blank=True)
    datos_legacy = models.JSONField(default=dict, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chofer"
        verbose_name_plural = "Choferes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} - {self.patente}"

    @property
    def porcentaje_liquidacion_decimal(self):
        porcentaje = self.porcentaje_liquidacion if self.porcentaje_liquidacion is not None else 60
        return Decimal(porcentaje) / Decimal("100")

    def rango_liquidacion(self, referencia=None):
        referencia = referencia or timezone.localdate()

        if self.tipo_liquidacion == "quincenal":
            desde = referencia - timedelta(days=14)
        elif self.tipo_liquidacion == "mensual":
            desde = referencia.replace(day=1)
        else:
            desde = referencia - timedelta(days=6)

        return desde, referencia


class Flete(models.Model):
    ESTADO_FLETE = [
        ("pendiente", "Pendiente"),
        ("en_curso", "En curso"),
        ("finalizado", "Finalizado"),
        ("cancelado", "Cancelado"),
    ]
    ESTADO_COBRO_CLIENTE = [
        ("no_exigible", "No exigible"),
        ("pendiente", "Pendiente"),
        ("cobrado", "Cobrado"),
        ("cancelado", "Cancelado"),
    ]
    ESTADO_PAGO_CHOFER = [
        ("no_liquidable", "No liquidable"),
        ("pendiente", "Pendiente"),
        ("liquidado", "Liquidado"),
        ("retenido", "Retenido"),
    ]
    FORMA_DE_PAGO = [
        ("efectivo", "Efectivo"),
        ("cuenta_corriente", "Cuenta corriente"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="fletes"
    )
    chofer = models.ForeignKey(
        Chofer,
        on_delete=models.PROTECT,
        related_name="fletes"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    direccion_origen = models.CharField(max_length=255)
    direccion_destino = models.CharField(max_length=255)
    ayudantes = models.PositiveIntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    forma_de_pago = models.CharField(max_length=20, choices=FORMA_DE_PAGO, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_FLETE, default="pendiente")
    estado_cobro_cliente = models.CharField(
        max_length=20,
        choices=ESTADO_COBRO_CLIENTE,
        default="no_exigible",
    )
    estado_pago_chofer = models.CharField(
        max_length=20,
        choices=ESTADO_PAGO_CHOFER,
        default="no_liquidable",
    )
    fecha_pago_chofer = models.DateTimeField(blank=True, null=True)
    observaciones_pago_chofer = models.TextField(blank=True, null=True)
    pagado = models.BooleanField(default=False)
    fecha_hora_en_curso = models.DateTimeField(blank=True, null=True)
    fecha_hora_finalizado = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Flete"
        verbose_name_plural = "Fletes"
        ordering = ["-fecha", "-hora_inicio"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["cliente"]),
            models.Index(fields=["chofer"]),
        ]

    def __str__(self):
        return f"Flete #{self.id} - {self.cliente.nombre} - {self.fecha}"

    @property
    def importe_chofer(self):
        porcentaje = getattr(self.chofer, "porcentaje_liquidacion_decimal", Decimal("60") / Decimal("100"))
        return (self.precio * porcentaje).quantize(Decimal("0.01"))

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.chofer_id or not self.fecha or not self.hora_inicio:
            return

        conflicto = Flete.objects.filter(
            chofer_id=self.chofer_id,
            fecha=self.fecha,
            hora_inicio=self.hora_inicio,
        ).exclude(id=self.id)

        if conflicto.exists():
            raise ValidationError(
                "Este chofer ya tiene un flete cargado en la misma fecha y hora."
            )

    def save(self, *args, **kwargs):
        estado_anterior = None
        if self.pk:
            estado_anterior = (
                Flete.objects
                .filter(pk=self.pk)
                .values_list("estado", flat=True)
                .first()
            )

        ahora = timezone.now()
        if self.estado == "en_curso" and estado_anterior != "en_curso" and not self.fecha_hora_en_curso:
            self.fecha_hora_en_curso = ahora
        if self.estado == "finalizado" and estado_anterior != "finalizado" and not self.fecha_hora_finalizado:
            self.fecha_hora_finalizado = ahora

        # Separamos la deuda del cliente de la futura liquidacion del chofer.
        if self.estado == "finalizado":
            if self.forma_de_pago == "efectivo":
                self.estado_cobro_cliente = "cobrado"
            elif self.estado_cobro_cliente in {"", None, "no_exigible"}:
                self.estado_cobro_cliente = "pendiente"

            if self.estado_pago_chofer == "no_liquidable":
                self.estado_pago_chofer = "pendiente"
        elif self.estado == "cancelado":
            self.estado_cobro_cliente = "cancelado"
            self.estado_pago_chofer = "no_liquidable"
        else:
            self.estado_cobro_cliente = "no_exigible"
            self.estado_pago_chofer = "no_liquidable"

        self.pagado = self.estado_cobro_cliente == "cobrado"

        super().save(*args, **kwargs)

        if self.estado == "finalizado":
            cobro, created = Cobro.objects.get_or_create(
                flete=self,
                defaults={
                    "monto": self.precio,
                    "metodo_pago": self.forma_de_pago or "efectivo",
                    "estado": "pagado" if self.estado_cobro_cliente == "cobrado" else "pendiente",
                    "fecha_pago": timezone.now() if self.estado_cobro_cliente == "cobrado" else None,
                },
            )
            cobro.monto = self.precio
            cobro.metodo_pago = self.forma_de_pago or cobro.metodo_pago or "efectivo"
            cobro.estado = {
                "pendiente": "pendiente",
                "cobrado": "pagado",
                "cancelado": "cancelado",
            }.get(self.estado_cobro_cliente, "pendiente")
            if cobro.estado == "pagado":
                cobro.fecha_pago = cobro.fecha_pago or timezone.now()
            else:
                cobro.fecha_pago = None
            cobro.save()

    @property
    def duracion(self):
        if not self.fecha_hora_en_curso or not self.fecha_hora_finalizado:
            return None
        return self.fecha_hora_finalizado - self.fecha_hora_en_curso

    @property
    def duracion_formateada(self):
        duracion = self.duracion
        if duracion is None:
            return None

        total_segundos = max(int(duracion.total_seconds()), 0)
        horas, resto = divmod(total_segundos, 3600)
        minutos, segundos = divmod(resto, 60)

        if horas:
            return f"{horas}h {minutos}m"
        if minutos:
            return f"{minutos}m {segundos}s"
        return f"{segundos}s"

    @property
    def saldo_pendiente_cliente(self):
        if self.estado == "finalizado" and self.estado_cobro_cliente == "pendiente":
            return self.precio
        return 0

    @property
    def fecha_cobro_cliente(self):
        try:
            return self.cobro.fecha_pago
        except Cobro.DoesNotExist:
            return None

    @property
    def observaciones_cobro_cliente(self):
        try:
            return self.cobro.observaciones
        except Cobro.DoesNotExist:
            return None

    def registrar_cobro_cliente(self, estado_cobro, observaciones=None, fecha_pago=None):
        self.estado_cobro_cliente = estado_cobro
        self.pagado = estado_cobro == "cobrado"
        self.save(update_fields=["estado_cobro_cliente", "pagado"])

        cobro = self.cobro
        campos_cobro = ["estado", "fecha_pago"]

        if estado_cobro == "cobrado":
            cobro.fecha_pago = fecha_pago or cobro.fecha_pago or timezone.now()
        else:
            cobro.fecha_pago = None

        if observaciones is not None:
            cobro.observaciones = observaciones.strip() or None
            campos_cobro.append("observaciones")

        cobro.save(update_fields=campos_cobro)

    def registrar_pago_chofer(self, estado_pago, observaciones=None, fecha_pago=None):
        self.estado_pago_chofer = estado_pago

        campos = ["estado_pago_chofer"]
        if estado_pago == "liquidado":
            self.fecha_pago_chofer = fecha_pago or self.fecha_pago_chofer or timezone.now()
        else:
            self.fecha_pago_chofer = None
        campos.append("fecha_pago_chofer")

        if observaciones is not None:
            self.observaciones_pago_chofer = observaciones.strip() or None
            campos.append("observaciones_pago_chofer")

        self.save(update_fields=campos)


class Cobro(models.Model):
    ESTADO_COBRO = [
        ("pendiente", "Pendiente"),
        ("pagado", "Pagado"),
        ("cancelado", "Cancelado"),
    ]

    METODO_PAGO = [
        ("efectivo", "Efectivo"),
        ("cuenta_corriente", "Cuenta corriente"),
    ]

    flete = models.OneToOneField(
        Flete,
        on_delete=models.CASCADE,
        related_name="cobro"
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO)
    estado = models.CharField(max_length=20, choices=ESTADO_COBRO, default="pendiente")
    fecha_pago = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cobro"
        verbose_name_plural = "Cobros"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Cobro de Flete #{self.flete.id} - {self.estado}"


class Viaje(models.Model):
    ESTADO_VIAJE = [
        ("pendiente", "Pendiente"),
        ("en_curso", "En curso"),
        ("finalizado", "Finalizado"),
        ("cancelado", "Cancelado"),
        ("sin_estado", "Sin estado"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="viajes",
        blank=True,
        null=True,
    )
    chofer = models.ForeignKey(
        Chofer,
        on_delete=models.SET_NULL,
        related_name="viajes",
        blank=True,
        null=True,
    )
    fecha = models.DateField(blank=True, null=True)
    origen = models.CharField(max_length=255, blank=True)
    destino = models.CharField(max_length=255, blank=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_VIAJE, default="sin_estado")
    observaciones = models.TextField(blank=True)
    codigo_legacy = models.CharField(max_length=50, unique=True)
    cliente_codigo_legacy = models.CharField(max_length=50, blank=True)
    chofer_codigo_legacy = models.CharField(max_length=50, blank=True)
    origen_legacy = models.CharField(max_length=30, default="VIAJES.DBF")
    datos_legacy = models.JSONField(default=dict, blank=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Viaje historico"
        verbose_name_plural = "Viajes historicos"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["cliente"]),
            models.Index(fields=["chofer"]),
            models.Index(fields=["codigo_legacy"]),
        ]

    def __str__(self):
        return f"Viaje {self.codigo_legacy} - {self.fecha or 'sin fecha'}"


class Factura(models.Model):
    ESTADO_FACTURA = [
        ("pendiente", "Pendiente"),
        ("pagada", "Pagada"),
        ("anulada", "Anulada"),
        ("sin_estado", "Sin estado"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="facturas",
        blank=True,
        null=True,
    )
    viaje = models.ForeignKey(
        Viaje,
        on_delete=models.SET_NULL,
        related_name="facturas",
        blank=True,
        null=True,
    )
    numero = models.CharField(max_length=50)
    fecha = models.DateField(blank=True, null=True)
    importe_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_FACTURA, default="sin_estado")
    observaciones = models.TextField(blank=True)
    codigo_legacy = models.CharField(max_length=50, unique=True)
    cliente_codigo_legacy = models.CharField(max_length=50, blank=True)
    viaje_codigo_legacy = models.CharField(max_length=50, blank=True)
    origen_legacy = models.CharField(max_length=30, default="FACTURAC.DBF")
    datos_legacy = models.JSONField(default=dict, blank=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Factura historica"
        verbose_name_plural = "Facturas historicas"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["cliente"]),
            models.Index(fields=["viaje"]),
            models.Index(fields=["codigo_legacy"]),
        ]

    def __str__(self):
        return f"Factura {self.numero}"
