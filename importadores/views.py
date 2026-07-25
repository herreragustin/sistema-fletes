from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .dbf import DBFError, DBFTable
from .models import (
    ChoferHistorico,
    ClienteHistorico,
    ReservaHistorica,
    ViajeHistorico,
)


def panel_sistema_anterior(request):
    return render(request, "importadores/panel_sistema_anterior.html", {
        "clientes_count": ClienteHistorico.objects.count(),
        "choferes_count": ChoferHistorico.objects.count(),
        "viajes_count": ViajeHistorico.objects.count(),
        "reservas_count": ReservaHistorica.objects.count(),
        "ultimos_viajes": ViajeHistorico.objects.select_related("cliente", "chofer").order_by("-fecha_importacion", "-id")[:8],
        "ultimas_reservas": ReservaHistorica.objects.select_related("cliente", "chofer").order_by("-fecha_importacion", "-id")[:8],
    })


def lista_clientes_historicos(request):
    q = request.GET.get("q", "").strip()
    activo = request.GET.get("activo", "")
    clientes = ClienteHistorico.objects.all()

    if q:
        clientes = clientes.filter(
            Q(nombre__icontains=q)
            | Q(telefono__icontains=q)
            | Q(direccion__icontains=q)
            | Q(codigo_legacy__icontains=q)
        )
    if activo == "1":
        clientes = clientes.filter(activo=True)
    elif activo == "0":
        clientes = clientes.filter(activo=False)

    page_obj = _paginate(request, clientes.order_by("nombre", "codigo_legacy"), 30)
    return render(request, "importadores/lista_clientes_historicos.html", {
        "page_obj": page_obj,
        "total": clientes.count(),
        "filtros": {"q": q, "activo": activo},
    })


def detalle_cliente_historico(request, pk):
    cliente = get_object_or_404(ClienteHistorico, pk=pk)
    viajes = cliente.viajes_historicos.order_by("-fecha", "-hora")[:20]
    reservas = cliente.reservas_historicas.order_by("-fecha", "-hora")[:20]
    return render(request, "importadores/detalle_cliente_historico.html", {
        "cliente": cliente,
        "viajes": viajes,
        "reservas": reservas,
    })


def lista_choferes_historicos(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    choferes = ChoferHistorico.objects.all()

    if q:
        choferes = choferes.filter(
            Q(nombre__icontains=q)
            | Q(telefono__icontains=q)
            | Q(patente__icontains=q)
            | Q(codigo_legacy__icontains=q)
        )
    if estado:
        choferes = choferes.filter(estado__iexact=estado)

    page_obj = _paginate(request, choferes.order_by("nombre", "codigo_legacy"), 30)
    return render(request, "importadores/lista_choferes_historicos.html", {
        "page_obj": page_obj,
        "total": choferes.count(),
        "filtros": {"q": q, "estado": estado},
    })


def detalle_chofer_historico(request, pk):
    chofer = get_object_or_404(ChoferHistorico, pk=pk)
    viajes = chofer.viajes_historicos.order_by("-fecha", "-hora")[:20]
    reservas = chofer.reservas_historicas.order_by("-fecha", "-hora")[:20]
    return render(request, "importadores/detalle_chofer_historico.html", {
        "chofer": chofer,
        "viajes": viajes,
        "reservas": reservas,
    })


def lista_viajes_historicos(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    viajes = ViajeHistorico.objects.select_related("cliente", "chofer").all()

    if q:
        viajes = viajes.filter(
            Q(codigo_legacy__icontains=q)
            | Q(origen__icontains=q)
            | Q(destino__icontains=q)
            | Q(cliente__nombre__icontains=q)
            | Q(chofer__nombre__icontains=q)
            | Q(cliente_codigo_legacy__icontains=q)
            | Q(chofer_codigo_legacy__icontains=q)
        )
    if estado:
        viajes = viajes.filter(estado=estado)
    if fecha_desde:
        viajes = viajes.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        viajes = viajes.filter(fecha__lte=fecha_hasta)

    page_obj = _paginate(request, viajes.order_by("-fecha", "-hora", "-codigo_legacy"), 40)
    return render(request, "importadores/lista_viajes_historicos.html", {
        "page_obj": page_obj,
        "total": viajes.count(),
        "estados": ViajeHistorico.ESTADO_VIAJE,
        "filtros": {"q": q, "estado": estado, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
    })


def detalle_viaje_historico(request, pk):
    viaje = get_object_or_404(ViajeHistorico.objects.select_related("cliente", "chofer"), pk=pk)
    return render(request, "importadores/detalle_viaje_historico.html", {"viaje": viaje})


def lista_reservas_historicas(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    reservas = ReservaHistorica.objects.select_related("cliente", "chofer").all()

    if q:
        reservas = reservas.filter(
            Q(codigo_legacy__icontains=q)
            | Q(origen__icontains=q)
            | Q(destino__icontains=q)
            | Q(cliente__nombre__icontains=q)
            | Q(chofer__nombre__icontains=q)
            | Q(cliente_codigo_legacy__icontains=q)
            | Q(chofer_codigo_legacy__icontains=q)
        )
    if estado:
        reservas = reservas.filter(estado=estado)
    if fecha_desde:
        reservas = reservas.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        reservas = reservas.filter(fecha__lte=fecha_hasta)

    page_obj = _paginate(request, reservas.order_by("-fecha", "-hora", "-codigo_legacy"), 40)
    return render(request, "importadores/lista_reservas_historicas.html", {
        "page_obj": page_obj,
        "total": reservas.count(),
        "estados": ReservaHistorica.ESTADO_RESERVA,
        "filtros": {"q": q, "estado": estado, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
    })


def detalle_reserva_historica(request, pk):
    reserva = get_object_or_404(ReservaHistorica.objects.select_related("cliente", "chofer"), pk=pk)
    return render(request, "importadores/detalle_reserva_historica.html", {"reserva": reserva})


def lista_legacy_dbf(request):
    base_dir = get_legacy_base_dir()
    archivos = []

    if base_dir.exists():
        for path in sorted(base_dir.rglob("*.DBF")):
            rel_path = path.relative_to(base_dir).as_posix()
            archivos.append({
                "nombre": path.name,
                "ruta": rel_path,
                "tamano": path.stat().st_size,
                "modificado": path.stat().st_mtime,
            })

    return render(request, "importadores/lista_legacy_dbf.html", {
        "base_dir": base_dir,
        "archivos": archivos,
        "total": len(archivos),
    })


def detalle_legacy_dbf(request):
    from django.conf import settings

    base_dir = get_legacy_base_dir()
    archivo = request.GET.get("archivo", "")
    pagina = max(to_int(request.GET.get("pagina"), 1), 1)
    por_pagina = min(max(to_int(request.GET.get("por_pagina"), 50), 10), 200)
    offset = (pagina - 1) * por_pagina
    error = None
    info = None
    filas = []
    campos = []

    try:
        path = resolve_legacy_path(base_dir, archivo)
        table = DBFTable(path, encoding="cp850")
        info = table.inspect()
        campos = [field.name for field in info["fields"]]
        for index, (row_number, record) in enumerate(table):
            if index < offset:
                continue
            if len(filas) >= por_pagina:
                break
            filas.append({"numero": row_number, "valores": [record.get(field) for field in campos]})
    except (ValueError, DBFError, OSError) as exc:
        error = str(exc)

    return render(request, "importadores/detalle_legacy_dbf.html", {
        "archivo": archivo,
        "campos": campos,
        "error": error,
        "filas": filas,
        "info": info,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "pagina_anterior": pagina - 1 if pagina > 1 else None,
        "pagina_siguiente": pagina + 1 if filas and len(filas) == por_pagina else None,
    })


def get_legacy_base_dir():
    from django.conf import settings

    return settings.BASE_DIR / "importslegacy"


def resolve_legacy_path(base_dir, archivo):
    if not archivo:
        raise ValueError("No se indico ningun archivo DBF.")

    path = (base_dir / archivo).resolve()
    base_resolved = base_dir.resolve()
    if base_resolved not in path.parents and path != base_resolved:
        raise ValueError("Ruta fuera de importslegacy.")
    if not path.exists() or path.suffix.upper() != ".DBF":
        raise ValueError("El archivo DBF no existe.")
    return path


def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _paginate(request, queryset, per_page):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("pagina"))
