from django.conf import settings
from django.shortcuts import render

from .dbf import DBFError, DBFTable


def lista_legacy_dbf(request):
    """Explorador manual de archivos DBF para diagnosticos futuros.

    Esta vista no esta conectada al panel principal. Para usarla temporalmente,
    incluir `path("legacy/", include("importadores.urls"))` en `config/urls.py`
    o en el urls principal del proyecto.
    """
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
    """Muestra una pagina de un DBF sin importarlo a la base nueva."""
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
            filas.append({
                "numero": row_number,
                "valores": [record.get(field) for field in campos],
            })
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
