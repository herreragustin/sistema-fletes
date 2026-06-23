from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404, redirect
from .models import Cobro, Flete, Cliente, Chofer, Factura, Viaje
from .forms import ClienteForm, ChoferForm, FleteForm


def _sumar_importe_chofer(fletes):
    return sum((flete.importe_chofer for flete in fletes), Decimal("0"))


def _direcciones_cliente(cliente, limite=20):
    direcciones = []
    vistas = set()

    def agregar(valor):
        if not valor:
            return
        texto = str(valor).strip()
        if not texto:
            return
        clave = texto.casefold()
        if clave in vistas:
            return
        vistas.add(clave)
        direcciones.append(texto)

    agregar(cliente.direccion)

    fletes = (
        Flete.objects.filter(cliente=cliente)
        .order_by("-fecha", "-hora_inicio", "-id")
        .values_list("direccion_origen", "direccion_destino")[:limite]
    )

    for origen, destino in fletes:
        agregar(origen)
        agregar(destino)

    return direcciones


def _periodo_anterior(tipo_liquidacion, fecha_desde):
    nuevo_hasta = fecha_desde - timedelta(days=1)
    if tipo_liquidacion == "quincenal":
        nuevo_desde = nuevo_hasta - timedelta(days=14)
    elif tipo_liquidacion == "mensual":
        nuevo_desde = nuevo_hasta.replace(day=1)
    else:
        nuevo_desde = nuevo_hasta - timedelta(days=6)
    return nuevo_desde, nuevo_hasta


def _resolver_periodo_liquidacion_con_movimientos(chofer, referencia=None):
    referencia = referencia or timezone.localdate()
    fecha_desde, fecha_hasta = chofer.rango_liquidacion(referencia)
    queryset = Flete.objects.filter(
        chofer=chofer,
        estado="finalizado",
    )

    if not queryset.exists():
        return fecha_desde, fecha_hasta, False

    if queryset.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta).exists():
        return fecha_desde, fecha_hasta, False

    fecha_minima = queryset.order_by("fecha").values_list("fecha", flat=True).first()
    periodo_es_historico = False

    while fecha_desde > fecha_minima:
        fecha_desde, fecha_hasta = _periodo_anterior(chofer.tipo_liquidacion, fecha_desde)
        periodo_es_historico = True
        if queryset.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta).exists():
            return fecha_desde, fecha_hasta, periodo_es_historico

    return fecha_desde, fecha_hasta, periodo_es_historico


def _mensajes_validacion_flete_para_estado(flete, estado_destino):
    mensajes_error = []
    origen = (flete.direccion_origen or "").strip()
    destino = (flete.direccion_destino or "").strip()
    precio = flete.precio

    if estado_destino in {"en_curso", "finalizado"} and not flete.chofer_id:
        if estado_destino == "en_curso":
            mensajes_error.append("No se puede iniciar un flete sin chofer asignado")
        else:
            mensajes_error.append("No se puede finalizar un flete sin chofer asignado")

    if estado_destino == "finalizado":
        if not origen:
            mensajes_error.append("No se puede finalizar un flete sin origen")
        if not destino:
            mensajes_error.append("No se puede finalizar un flete sin destino")
        if precio is None or precio <= 0:
            mensajes_error.append("No se puede finalizar un flete con precio menor o igual a cero")

    return mensajes_error


def panel_inicio(request):
    hoy = timezone.localdate()
    fletes_hoy = (
        Flete.objects.select_related("cliente", "chofer")
        .filter(fecha=hoy)
        .order_by("hora_inicio", "id")
    )
    reservas_futuras = (
        Flete.objects.select_related("cliente", "chofer")
        .filter(fecha__gt=hoy)
        .order_by("fecha", "hora_inicio", "id")
    )
    ultimos_fletes = Flete.objects.select_related("cliente", "chofer").order_by("-fecha_creacion", "-id")[:5]
    fletes_cobro_pendiente = Flete.objects.filter(
        estado="finalizado",
        forma_de_pago="cuenta_corriente",
        estado_cobro_cliente="pendiente",
    )
    fletes_liquidacion_pendiente = Flete.objects.select_related("chofer").filter(
        estado="finalizado",
        estado_pago_chofer="pendiente",
    )
    clientes_con_cobranza_pendiente = Cliente.objects.filter(
        fletes__estado="finalizado",
        fletes__forma_de_pago="cuenta_corriente",
        fletes__estado_cobro_cliente="pendiente",
    ).distinct().count()
    choferes_con_liquidacion_pendiente = Chofer.objects.filter(
        fletes__estado="finalizado",
        fletes__estado_pago_chofer="pendiente",
    ).distinct().count()
    total_cobranza_pendiente = fletes_cobro_pendiente.aggregate(total=Sum("precio"))["total"] or 0
    total_liquidacion_pendiente = _sumar_importe_chofer(fletes_liquidacion_pendiente)

    return render(request, "core/panel_inicio.html", {
        "hoy": hoy,
        "fletes_hoy": fletes_hoy,
        "reservas_futuras": reservas_futuras,
        "ultimos_fletes": ultimos_fletes,
        "clientes_con_cobranza_pendiente": clientes_con_cobranza_pendiente,
        "choferes_con_liquidacion_pendiente": choferes_con_liquidacion_pendiente,
        "total_cobranza_pendiente": total_cobranza_pendiente,
        "total_liquidacion_pendiente": total_liquidacion_pendiente,
    })


def reportes(request):
    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")

    fletes = Flete.objects.filter(estado="finalizado")

    if fecha_desde:
        fletes = fletes.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        fletes = fletes.filter(fecha__lte=fecha_hasta)

    total_facturado = fletes.aggregate(total=Sum("precio"))["total"] or 0
    total_cobrado = fletes.filter(estado_cobro_cliente="cobrado").aggregate(total=Sum("precio"))["total"] or 0
    total_pendiente_cobro = fletes.filter(estado_cobro_cliente="pendiente").aggregate(total=Sum("precio"))["total"] or 0

    total_a_pagar_choferes = _sumar_importe_chofer(fletes)
    total_pagado_choferes = _sumar_importe_chofer(fletes.filter(estado_pago_chofer="liquidado"))
    total_pendiente_pago_choferes = _sumar_importe_chofer(fletes.filter(estado_pago_chofer="pendiente"))

    resultado_estimado = total_cobrado - total_a_pagar_choferes

    return render(request, "core/reportes.html", {
        "total_facturado": total_facturado,
        "total_cobrado": total_cobrado,
        "total_pendiente_cobro": total_pendiente_cobro,
        "total_a_pagar_choferes": total_a_pagar_choferes,
        "total_pagado_choferes": total_pagado_choferes,
        "total_pendiente_pago_choferes": total_pendiente_pago_choferes,
        "resultado_estimado": resultado_estimado,
        "filtros": {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    })


def lista_fletes(request):
    fletes = Flete.objects.select_related("cliente", "chofer").all()
    clientes = Cliente.objects.order_by("nombre")
    choferes = Chofer.objects.order_by("nombre")

    # filtros
    filtro_rapido = request.GET.get("filtro")
    fecha = request.GET.get("fecha")
    estado = request.GET.get("estado")
    cliente = request.GET.get("cliente")
    chofer = request.GET.get("chofer")
    forma_de_pago = request.GET.get("forma_de_pago")

    if filtro_rapido == "hoy":
        fletes = fletes.filter(fecha=timezone.localdate())
    elif filtro_rapido == "pendientes":
        fletes = fletes.filter(estado="pendiente")
    elif filtro_rapido == "en_curso":
        fletes = fletes.filter(estado="en_curso")
    elif filtro_rapido == "finalizados":
        fletes = fletes.filter(estado="finalizado")
    elif filtro_rapido == "cancelados":
        fletes = fletes.filter(estado="cancelado")
    elif filtro_rapido == "sin_chofer":
        fletes = fletes.filter(chofer__isnull=True)

    if fecha:
        fletes = fletes.filter(fecha=fecha)

    if estado:
        fletes = fletes.filter(estado=estado)

    if cliente:
        fletes = fletes.filter(cliente_id=cliente)

    if chofer:
        fletes = fletes.filter(chofer_id=chofer)

    if forma_de_pago:
        fletes = fletes.filter(forma_de_pago=forma_de_pago)

    fletes = fletes.order_by("-fecha", "-hora_inicio")
    cliente_seleccionado = clientes.filter(id=cliente).first() if cliente else None
    chofer_seleccionado = choferes.filter(id=chofer).first() if chofer else None

    filtros_actuales = {
        "filtro": filtro_rapido,
        "fecha": fecha,
        "estado": estado,
        "cliente": cliente,
        "chofer": chofer,
        "forma_de_pago": forma_de_pago,
    }

    base_params = request.GET.copy()
    filtros_rapidos = []
    for value, label in [
        ("", "Todos"),
        ("hoy", "Hoy"),
        ("pendientes", "Pendientes"),
        ("en_curso", "En curso"),
        ("finalizados", "Finalizados"),
        ("cancelados", "Cancelados"),
        ("sin_chofer", "Sin chofer asignado"),
    ]:
        params = base_params.copy()
        if value:
            params["filtro"] = value
        else:
            params.pop("filtro", None)
        filtros_rapidos.append({
            "label": label,
            "value": value,
            "querystring": urlencode([(key, item) for key, values in params.lists() for item in values]),
            "activo": (filtro_rapido or "") == value,
        })

    context = {
        "fletes": fletes,
        "clientes": clientes,
        "choferes": choferes,
        "formas_de_pago": Flete.FORMA_DE_PAGO,
        "filtros": filtros_actuales,
        "filtros_rapidos": filtros_rapidos,
        "cliente_seleccionado": cliente_seleccionado,
        "chofer_seleccionado": chofer_seleccionado,
    }

    return render(request, "core/lista_fletes_panel.html", context)


def crear_flete(request):
    if request.method == "POST":
        form = FleteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("lista_fletes")
    else:
        form = FleteForm()

    return render(request, "core/formulario_flete.html", {
        "form": form,
        "titulo": "Nuevo flete",
        "texto_boton": "Crear flete",
    })


def duplicar_flete(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id)
    form = FleteForm(initial={
        "cliente": flete.cliente_id,
        "chofer": flete.chofer_id,
        "fecha": timezone.localdate(),
        "hora_inicio": flete.hora_inicio,
        "direccion_origen": flete.direccion_origen,
        "direccion_destino": flete.direccion_destino,
        "ayudantes": flete.ayudantes,
        "precio": flete.precio,
        "forma_de_pago": flete.forma_de_pago,
        "estado": "pendiente",
    })

    return render(request, "core/formulario_flete.html", {
        "form": form,
        "titulo": f"Duplicar flete #{flete.id}",
        "texto_boton": "Crear flete",
    })


def direcciones_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    return JsonResponse({"direcciones": _direcciones_cliente(cliente)})


@require_POST
def finalizar_flete(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id)
    if flete.estado == "en_curso":
        errores = _mensajes_validacion_flete_para_estado(flete, "finalizado")
        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect(request.POST.get("next") or "lista_fletes")
        flete.estado = "finalizado"
        flete.save()
    return redirect(request.POST.get("next") or "lista_fletes")


@require_POST
def cambiar_estado_flete(request, flete_id, estado):
    estados_validos = {value for value, _ in Flete.ESTADO_FLETE}
    if estado not in estados_validos:
        return redirect(request.POST.get("next") or "lista_fletes")

    flete = get_object_or_404(Flete, id=flete_id)
    transiciones_validas = {
        "pendiente": {"en_curso", "cancelado"},
        "en_curso": {"pendiente", "finalizado", "cancelado"},
        "cancelado": {"pendiente", "en_curso"},
        "finalizado": {"en_curso", "pendiente", "cancelado"},
    }

    if estado in transiciones_validas.get(flete.estado, set()):
        errores = _mensajes_validacion_flete_para_estado(flete, estado)
        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect(request.POST.get("next") or "lista_fletes")
        flete.estado = estado
        flete.save()

    return redirect(request.POST.get("next") or "lista_fletes")


def editar_flete(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id)

    if request.method == "POST":
        form = FleteForm(request.POST, instance=flete)
        if form.is_valid():
            form.save()
            return redirect("lista_fletes")
    else:
        form = FleteForm(instance=flete)

    return render(request, "core/formulario_flete.html", {
        "form": form,
        "flete": flete,
        "titulo": f"Editar flete #{flete.id}",
        "texto_boton": "Guardar cambios",
    })


def lista_clientes(request):
    clientes = Cliente.objects.all()
    estado = request.GET.get("estado")
    cliente = request.GET.get("cliente")

    if estado == "activo":
        clientes = clientes.filter(activo=True)
    elif estado == "inactivo":
        clientes = clientes.filter(activo=False)

    if cliente:
        clientes = clientes.filter(id=cliente)

    return render(request, "core/lista_clientes.html", {
        "clientes": clientes,
        "clientes_filtro": Cliente.objects.all(),
        "filtros": {"estado": estado, "cliente": cliente},
    })


def crear_cliente(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("lista_clientes")
    else:
        form = ClienteForm(initial={"activo": True})

    return render(request, "core/formulario_cliente.html", {
        "form": form,
        "titulo": "Nuevo cliente",
        "texto_boton": "Crear cliente",
    })


def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect("lista_clientes")
    else:
        form = ClienteForm(instance=cliente)

    return render(request, "core/formulario_cliente.html", {
        "form": form,
        "cliente": cliente,
        "titulo": f"Editar cliente #{cliente.id}",
        "texto_boton": "Guardar cambios",
    })


def detalle_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    fletes_qs = Flete.objects.select_related("chofer").filter(cliente=cliente).order_by("-fecha", "-hora_inicio", "-id")
    ultimos_fletes = list(fletes_qs[:10])
    total_fletes = fletes_qs.count()
    total_finalizados = fletes_qs.filter(estado="finalizado").count()
    ultimo_flete = fletes_qs.first()
    total_facturado = fletes_qs.filter(estado="finalizado").aggregate(total=Sum("precio"))["total"] or 0
    total_cobrado = fletes_qs.filter(estado="finalizado", estado_cobro_cliente="cobrado").aggregate(total=Sum("precio"))["total"] or 0
    total_pendiente = fletes_qs.filter(estado="finalizado", estado_cobro_cliente="pendiente").aggregate(total=Sum("precio"))["total"] or 0

    return render(request, "core/detalle_cliente.html", {
        "cliente": cliente,
        "total_fletes": total_fletes,
        "total_finalizados": total_finalizados,
        "ultimo_flete": ultimo_flete,
        "total_facturado": total_facturado,
        "total_cobrado": total_cobrado,
        "total_pendiente": total_pendiente,
        "ultimas_direcciones": _direcciones_cliente(cliente, limite=10),
        "ultimos_fletes": ultimos_fletes,
    })


def lista_choferes(request):
    choferes = Chofer.objects.all()
    estado = request.GET.get("estado")
    chofer = request.GET.get("chofer")
    porcentaje = request.GET.get("porcentaje")

    if estado:
        choferes = choferes.filter(estado=estado)

    if chofer:
        choferes = choferes.filter(id=chofer)

    if porcentaje == "estandar":
        choferes = choferes.filter(porcentaje_liquidacion=60)
    elif porcentaje == "excepcion":
        choferes = choferes.exclude(porcentaje_liquidacion=60)

    return render(request, "core/lista_choferes.html", {
        "choferes": choferes,
        "choferes_filtro": Chofer.objects.all(),
        "filtros": {"estado": estado, "chofer": chofer, "porcentaje": porcentaje},
    })


def liquidacion_choferes(request):
    chofer_id = request.GET.get("chofer")
    choferes_qs = Chofer.objects.order_by("nombre")
    if chofer_id:
        choferes_qs = choferes_qs.filter(id=chofer_id)

    choferes = []
    viajes_pendientes = []
    total_pendiente = Decimal("0")
    hoy = timezone.localdate()

    for chofer in choferes_qs:
        tiene_movimientos_historicos = Flete.objects.filter(
            chofer=chofer,
            estado="finalizado",
        ).exists()
        fecha_desde, fecha_hasta, periodo_es_historico = _resolver_periodo_liquidacion_con_movimientos(chofer, hoy)
        fletes_periodo = list(
            Flete.objects.select_related("cliente", "chofer").filter(
                chofer=chofer,
                estado="finalizado",
                fecha__gte=fecha_desde,
                fecha__lte=fecha_hasta,
            ).order_by("-fecha", "-hora_inicio")
        )
        if not fletes_periodo and not (chofer_id or tiene_movimientos_historicos):
            continue

        pendientes = [flete for flete in fletes_periodo if flete.estado_pago_chofer == "pendiente"]
        pagados = [flete for flete in fletes_periodo if flete.estado_pago_chofer == "liquidado"]

        chofer.total_pendiente = _sumar_importe_chofer(pendientes)
        chofer.viajes_pendientes_count = len(pendientes)
        chofer.viajes_pagados_count = len(pagados)
        chofer.movimientos_liquidables_count = len(fletes_periodo)
        chofer.periodo_desde = fecha_desde
        chofer.periodo_hasta = fecha_hasta
        chofer.periodo_es_historico = periodo_es_historico
        choferes.append(chofer)

        viajes_pendientes.extend(pendientes)
        total_pendiente += chofer.total_pendiente

    viajes_pendientes.sort(key=lambda flete: (flete.fecha, flete.hora_inicio), reverse=True)

    return render(request, "core/liquidacion_choferes.html", {
        "choferes": choferes,
        "choferes_filtro": Chofer.objects.order_by("nombre"),
        "viajes_pendientes": viajes_pendientes,
        "total_pendiente": total_pendiente,
        "filtros": {
            "chofer": chofer_id,
        },
    })


def detalle_liquidacion_chofer(request, chofer_id):
    chofer = get_object_or_404(Chofer, id=chofer_id)
    estado_pago = request.GET.get("estado_pago")
    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")
    hoy = timezone.localdate()

    fecha_desde_default, fecha_hasta_default, periodo_es_historico = _resolver_periodo_liquidacion_con_movimientos(chofer, hoy)
    fecha_desde_aplicada = fecha_desde or fecha_desde_default.isoformat()
    fecha_hasta_aplicada = fecha_hasta or fecha_hasta_default.isoformat()

    fletes = Flete.objects.select_related("cliente").filter(
        chofer=chofer,
        estado="finalizado",
    )

    fletes = fletes.filter(
        fecha__gte=fecha_desde_aplicada,
        fecha__lte=fecha_hasta_aplicada,
    )

    if estado_pago:
        fletes = fletes.filter(estado_pago_chofer=estado_pago)

    fletes = list(fletes.order_by("-fecha", "-hora_inicio"))
    total_periodo = _sumar_importe_chofer(fletes)
    total_pagado = _sumar_importe_chofer([flete for flete in fletes if flete.estado_pago_chofer == "liquidado"])
    total_pendiente = _sumar_importe_chofer([flete for flete in fletes if flete.estado_pago_chofer == "pendiente"])
    pendientes_periodo = list(
        Flete.objects.filter(
            chofer=chofer,
            estado="finalizado",
            estado_pago_chofer="pendiente",
            fecha__gte=fecha_desde_aplicada,
            fecha__lte=fecha_hasta_aplicada,
        ).order_by("-fecha", "-hora_inicio")
    )
    pendientes_periodo_count = len(pendientes_periodo)
    total_pendiente_periodo = _sumar_importe_chofer(pendientes_periodo)

    return render(request, "core/detalle_liquidacion_chofer.html", {
        "chofer": chofer,
        "fletes": fletes,
        "total_periodo": total_periodo,
        "total_pagado": total_pagado,
        "total_pendiente": total_pendiente,
        "pendientes_periodo_count": pendientes_periodo_count,
        "total_pendiente_periodo": total_pendiente_periodo,
        "estados_pago": [estado for estado in Flete.ESTADO_PAGO_CHOFER if estado[0] != "no_liquidable"],
        "periodo_automatico": {
            "desde": fecha_desde_default,
            "hasta": fecha_hasta_default,
            "es_historico": periodo_es_historico,
        },
        "filtros": {
            "estado_pago": estado_pago,
            "fecha_desde": fecha_desde_aplicada,
            "fecha_hasta": fecha_hasta_aplicada,
        },
    })


def crear_chofer(request):
    if request.method == "POST":
        form = ChoferForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("lista_choferes")
    else:
        form = ChoferForm(initial={"estado": "activo"})

    return render(request, "core/formulario_chofer.html", {
        "form": form,
        "titulo": "Nuevo chofer",
        "texto_boton": "Crear chofer",
    })


def editar_chofer(request, chofer_id):
    chofer = get_object_or_404(Chofer, id=chofer_id)

    if request.method == "POST":
        form = ChoferForm(request.POST, instance=chofer)
        if form.is_valid():
            form.save()
            return redirect("lista_choferes")
    else:
        form = ChoferForm(instance=chofer)

    return render(request, "core/formulario_chofer.html", {
        "form": form,
        "chofer": chofer,
        "titulo": f"Editar chofer #{chofer.id}",
        "texto_boton": "Guardar cambios",
    })


def detalle_chofer(request, chofer_id):
    chofer = get_object_or_404(Chofer, id=chofer_id)
    fletes_qs = Flete.objects.select_related("cliente").filter(chofer=chofer).order_by("-fecha", "-hora_inicio", "-id")
    ultimos_fletes = list(fletes_qs[:10])
    total_fletes = fletes_qs.count()
    total_finalizados = fletes_qs.filter(estado="finalizado").count()
    ultimo_flete = fletes_qs.first()
    fletes_finalizados = list(fletes_qs.filter(estado="finalizado"))
    total_producido = sum((flete.precio for flete in fletes_finalizados), Decimal("0"))
    total_a_pagar = _sumar_importe_chofer(fletes_finalizados)
    total_pagado = _sumar_importe_chofer([flete for flete in fletes_finalizados if flete.estado_pago_chofer == "liquidado"])
    total_pendiente = _sumar_importe_chofer([flete for flete in fletes_finalizados if flete.estado_pago_chofer == "pendiente"])

    return render(request, "core/detalle_chofer.html", {
        "chofer": chofer,
        "total_fletes": total_fletes,
        "total_finalizados": total_finalizados,
        "ultimo_flete": ultimo_flete,
        "total_producido": total_producido,
        "total_a_pagar": total_a_pagar,
        "total_pagado": total_pagado,
        "total_pendiente": total_pendiente,
        "ultimos_fletes": ultimos_fletes,
    })


def facturacion(request):
    fletes = Flete.objects.select_related("cliente", "chofer", "cobro").filter(estado="finalizado")
    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")
    cliente = request.GET.get("cliente")
    chofer = request.GET.get("chofer")
    forma_de_pago = request.GET.get("forma_de_pago")
    estado_cobro = request.GET.get("estado_cobro")
    estado_pago = request.GET.get("estado_pago")
    busqueda = request.GET.get("q", "").strip()

    if fecha_desde:
        fletes = fletes.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        fletes = fletes.filter(fecha__lte=fecha_hasta)

    if cliente:
        fletes = fletes.filter(cliente_id=cliente)

    if chofer:
        fletes = fletes.filter(chofer_id=chofer)

    if forma_de_pago:
        fletes = fletes.filter(forma_de_pago=forma_de_pago)

    if estado_cobro:
        fletes = fletes.filter(estado_cobro_cliente=estado_cobro)

    if estado_pago == "pagado":
        fletes = fletes.filter(estado_cobro_cliente="cobrado")
    elif estado_pago == "pendiente":
        fletes = fletes.filter(estado_cobro_cliente="pendiente")

    if busqueda:
        filtros_busqueda = (
            Q(cliente__nombre__icontains=busqueda)
            | Q(chofer__nombre__icontains=busqueda)
            | Q(direccion_origen__icontains=busqueda)
            | Q(direccion_destino__icontains=busqueda)
        )
        if busqueda.isdigit():
            filtros_busqueda |= Q(id=int(busqueda))
        fletes = fletes.filter(filtros_busqueda)

    total_facturable = fletes.aggregate(total=Sum("precio"))["total"] or 0
    total_pendiente = fletes.filter(estado_cobro_cliente="pendiente").aggregate(total=Sum("precio"))["total"] or 0
    total_pagado = fletes.filter(estado_cobro_cliente="cobrado").aggregate(total=Sum("precio"))["total"] or 0
    fletes = fletes.order_by("-fecha", "-hora_inicio")

    return render(request, "core/facturacion.html", {
        "fletes": fletes,
        "clientes": Cliente.objects.order_by("nombre"),
        "choferes": Chofer.objects.order_by("nombre"),
        "formas_de_pago": Flete.FORMA_DE_PAGO,
        "estados_cobro": [estado for estado in Flete.ESTADO_COBRO_CLIENTE if estado[0] != "no_exigible"],
        "total_facturable": total_facturable,
        "total_pendiente": total_pendiente,
        "total_pagado": total_pagado,
        "filtros": {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "cliente": cliente,
            "chofer": chofer,
            "forma_de_pago": forma_de_pago,
            "estado_cobro": estado_cobro,
            "estado_pago": estado_pago,
            "q": busqueda,
        },
    })


@require_POST
def marcar_cobro_pagado(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id, estado="finalizado")
    flete.registrar_cobro_cliente(
        "cobrado",
        fecha_pago=timezone.now(),
    )
    return redirect(request.POST.get("next") or "facturacion")


@require_POST
def marcar_cobro_pendiente(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id, estado="finalizado")
    flete.registrar_cobro_cliente("pendiente")
    return redirect(request.POST.get("next") or "facturacion")


def cuenta_corriente_clientes(request):
    cliente_id = request.GET.get("cliente")
    clientes = Cliente.objects.order_by("nombre").annotate(
        saldo_adeudado=Coalesce(
            Sum(
                "fletes__precio",
                filter=Q(
                    fletes__estado="finalizado",
                    fletes__forma_de_pago="cuenta_corriente",
                    fletes__estado_cobro_cliente="pendiente",
                ),
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        fletes_pendientes_count=Count(
            "fletes",
            filter=Q(
                fletes__estado="finalizado",
                fletes__forma_de_pago="cuenta_corriente",
                fletes__estado_cobro_cliente="pendiente",
            ),
            distinct=True,
        ),
        fletes_cobrados_count=Count(
            "fletes",
            filter=Q(
                fletes__estado="finalizado",
                fletes__forma_de_pago="cuenta_corriente",
                fletes__estado_cobro_cliente="cobrado",
            ),
            distinct=True,
        ),
        movimientos_cuenta_corriente_count=Count(
            "fletes",
            filter=Q(
                fletes__estado="finalizado",
                fletes__forma_de_pago="cuenta_corriente",
            ),
            distinct=True,
        ),
    )

    fletes_pendientes = Flete.objects.select_related("cliente", "chofer", "cobro").filter(
        estado="finalizado",
        forma_de_pago="cuenta_corriente",
        estado_cobro_cliente="pendiente",
    )

    if cliente_id:
        clientes = clientes.filter(id=cliente_id)
        fletes_pendientes = fletes_pendientes.filter(cliente_id=cliente_id)
    else:
        clientes = clientes.filter(movimientos_cuenta_corriente_count__gt=0)

    total_adeudado = fletes_pendientes.aggregate(total=Sum("precio"))["total"] or 0

    return render(request, "core/cuenta_corriente_clientes.html", {
        "clientes": clientes,
        "clientes_filtro": Cliente.objects.order_by("nombre"),
        "fletes_pendientes": fletes_pendientes.order_by("-fecha", "-hora_inicio"),
        "total_adeudado": total_adeudado,
        "filtros": {
            "cliente": cliente_id,
        },
    })


def detalle_cuenta_corriente_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    estado_cobro = request.GET.get("estado_cobro")
    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")

    fletes = Flete.objects.select_related("chofer", "cobro").filter(
        cliente=cliente,
        estado="finalizado",
        forma_de_pago="cuenta_corriente",
    )

    if fecha_desde:
        fletes = fletes.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        fletes = fletes.filter(fecha__lte=fecha_hasta)

    if estado_cobro:
        fletes = fletes.filter(estado_cobro_cliente=estado_cobro)

    total_facturado = fletes.aggregate(total=Sum("precio"))["total"] or 0
    total_cobrado = fletes.filter(estado_cobro_cliente="cobrado").aggregate(total=Sum("precio"))["total"] or 0
    total_pendiente = fletes.filter(estado_cobro_cliente="pendiente").aggregate(total=Sum("precio"))["total"] or 0
    pendientes_periodo = Flete.objects.filter(
        cliente=cliente,
        estado="finalizado",
        forma_de_pago="cuenta_corriente",
        estado_cobro_cliente="pendiente",
    )
    if fecha_desde:
        pendientes_periodo = pendientes_periodo.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        pendientes_periodo = pendientes_periodo.filter(fecha__lte=fecha_hasta)
    pendientes_periodo = list(pendientes_periodo.order_by("-fecha", "-hora_inicio"))
    pendientes_periodo_count = len(pendientes_periodo)
    total_pendiente_periodo = sum((flete.precio for flete in pendientes_periodo), Decimal("0"))

    return render(request, "core/detalle_cuenta_corriente_cliente.html", {
        "cliente": cliente,
        "fletes": fletes.order_by("-fecha", "-hora_inicio"),
        "total_facturado": total_facturado,
        "total_cobrado": total_cobrado,
        "total_pendiente": total_pendiente,
        "pendientes_periodo_count": pendientes_periodo_count,
        "total_pendiente_periodo": total_pendiente_periodo,
        "estados_cobro": [estado for estado in Flete.ESTADO_COBRO_CLIENTE if estado[0] != "no_exigible"],
        "filtros": {
            "estado_cobro": estado_cobro,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    })


@require_POST
def cerrar_cobranza_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    fecha_desde = request.POST.get("fecha_desde")
    fecha_hasta = request.POST.get("fecha_hasta")
    fecha_desde = None if fecha_desde in {"", "None", None} else fecha_desde
    fecha_hasta = None if fecha_hasta in {"", "None", None} else fecha_hasta

    pendientes = Flete.objects.filter(
        cliente=cliente,
        estado="finalizado",
        forma_de_pago="cuenta_corriente",
        estado_cobro_cliente="pendiente",
    )
    if fecha_desde:
        pendientes = pendientes.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        pendientes = pendientes.filter(fecha__lte=fecha_hasta)

    pendientes = list(pendientes)

    if not pendientes:
        messages.info(request, "Sin viajes pendientes de cobro en este periodo.")
        return redirect(request.POST.get("next") or "detalle_cuenta_corriente_cliente", cliente_id=cliente.id)

    ahora = timezone.now()
    for flete in pendientes:
        flete.registrar_cobro_cliente("cobrado", fecha_pago=ahora)

    messages.success(request, f"Se marcaron {len(pendientes)} viajes como cobrados.")
    return redirect(request.POST.get("next") or "detalle_cuenta_corriente_cliente", cliente_id=cliente.id)


@require_POST
def cerrar_liquidacion_chofer(request, chofer_id):
    chofer = get_object_or_404(Chofer, id=chofer_id)
    fecha_desde = request.POST.get("fecha_desde")
    fecha_hasta = request.POST.get("fecha_hasta")
    fecha_desde = None if fecha_desde in {"", "None", None} else fecha_desde
    fecha_hasta = None if fecha_hasta in {"", "None", None} else fecha_hasta

    if not fecha_desde or not fecha_hasta:
        fecha_desde_default, fecha_hasta_default, _ = _resolver_periodo_liquidacion_con_movimientos(chofer, timezone.localdate())
        fecha_desde = fecha_desde or fecha_desde_default.isoformat()
        fecha_hasta = fecha_hasta or fecha_hasta_default.isoformat()

    pendientes = list(
        Flete.objects.filter(
            chofer=chofer,
            estado="finalizado",
            estado_pago_chofer="pendiente",
            fecha__gte=fecha_desde,
            fecha__lte=fecha_hasta,
        )
    )

    if not pendientes:
        messages.info(request, "Sin viajes pendientes en este periodo.")
        return redirect(request.POST.get("next") or "detalle_liquidacion_chofer", chofer_id=chofer.id)

    ahora = timezone.now()
    flete_ids = [flete.id for flete in pendientes]
    Flete.objects.filter(id__in=flete_ids).update(
        estado_pago_chofer="liquidado",
        fecha_pago_chofer=ahora,
    )

    messages.success(request, f"Se marcaron {len(flete_ids)} viajes como pagados.")
    return redirect(request.POST.get("next") or "detalle_liquidacion_chofer", chofer_id=chofer.id)


@require_POST
def marcar_pago_chofer_pagado(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id, estado="finalizado")
    flete.registrar_pago_chofer(
        "liquidado",
        fecha_pago=timezone.now(),
    )
    return redirect(request.POST.get("next") or "liquidacion_choferes")


@require_POST
def marcar_pago_chofer_pendiente(request, flete_id):
    flete = get_object_or_404(Flete, id=flete_id, estado="finalizado")
    flete.registrar_pago_chofer("pendiente")
    return redirect(request.POST.get("next") or "liquidacion_choferes")


def lista_viajes(request):
    viajes = Viaje.objects.select_related("cliente", "chofer").all()
    fecha = request.GET.get("fecha")
    estado = request.GET.get("estado")
    cliente = request.GET.get("cliente")
    chofer = request.GET.get("chofer")

    if fecha:
        viajes = viajes.filter(fecha=fecha)
    if estado:
        viajes = viajes.filter(estado=estado)
    if cliente:
        viajes = viajes.filter(cliente_id=cliente)
    if chofer:
        viajes = viajes.filter(chofer_id=chofer)

    return render(request, "core/lista_viajes.html", {
        "viajes": viajes,
        "clientes": Cliente.objects.all(),
        "choferes": Chofer.objects.all(),
        "estados": Viaje.ESTADO_VIAJE,
        "filtros": {"fecha": fecha, "estado": estado, "cliente": cliente, "chofer": chofer},
    })


def lista_facturas(request):
    facturas = Factura.objects.select_related("cliente", "viaje").all()
    fecha = request.GET.get("fecha")
    estado = request.GET.get("estado")
    cliente = request.GET.get("cliente")
    chofer = request.GET.get("chofer")

    if fecha:
        facturas = facturas.filter(fecha=fecha)
    if estado:
        facturas = facturas.filter(estado=estado)
    if cliente:
        facturas = facturas.filter(cliente_id=cliente)
    if chofer:
        facturas = facturas.filter(viaje__chofer_id=chofer)

    return render(request, "core/lista_facturas.html", {
        "facturas": facturas,
        "clientes": Cliente.objects.all(),
        "choferes": Chofer.objects.all(),
        "estados": Factura.ESTADO_FACTURA,
        "filtros": {"fecha": fecha, "estado": estado, "cliente": cliente, "chofer": chofer},
    })
