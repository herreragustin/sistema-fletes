import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from time import sleep

from django.db import IntegrityError, OperationalError

from core.models import Chofer, Cliente, Factura, Viaje

from .dbf import DBFTable


LOGGER = logging.getLogger("importadores.dbf")

DEFAULT_DBF_FILES = {
    "clientes": "CLIENTES.DBF",
    "choferes": "CHOFERES.DBF",
    "viajes": "VIAJES.DBF",
    "facturas": "FACTURAC.DBF",
}

FIELD_ALIASES = {
    "codigo": ("CODIGO", "COD", "ID", "NRO", "NUMERO", "CLIENTE", "CHOFER", "VIAJE", "VIAJ", "MOVIL"),
    "nombre": ("NAME", "NOMBRE", "RAZON", "RAZONSOC", "RAZON_SOC", "APELLIDO", "APELL", "NOMAPE", "DESCRIP"),
    "telefono": ("TELEF", "TELEFONO", "TEL", "TEL_CHOF", "CELULAR", "CEL", "FONO"),
    "direccion": ("CALLE_CLI", "DIRECCION", "DOMICILIO", "DOM", "DIR", "DESDE"),
    "dni": ("NRODOC", "DNI", "DOCUMENTO", "DOC", "CUIT", "CUIL"),
    "registro": ("NROREGIS", "REGISTRO", "LICENCIA", "CARNET"),
    "vehiculo": ("MARCAUT", "VEHICULO", "CAMION", "UNIDAD"),
    "patente": ("NROPAT", "PATENTE", "DOMINIO"),
    "seguro": ("COMPANIA", "SEGURO", "POLIZA"),
    "fecha": ("FECHA", "FEC", "FE_VIAJE", "FECVIAJE", "FECHA_VIA"),
    "origen": ("DESDEORI", "DESDE", "ORIGEN", "CARGA", "DIR_ORIG", "REMITO"),
    "destino": ("DESTIORI", "DESTINO", "HASTA", "DESCARGA", "DIR_DEST"),
    "importe": ("IMPORTEORI", "VALORVIAJE", "CONTADO", "CTACTE", "VAL", "IMPORTE", "TOTAL", "PRECIO", "MONTO", "VALOR"),
    "estado": ("CANCELADA", "LIQUIDADA", "STATUS", "ACTIVO", "ESTADO", "SITUACION"),
    "cliente_codigo": ("TELEF", "CODCLI", "CLIENTE", "IDCLI", "CLI", "C_CLIENTE", "CENCOS"),
    "chofer_codigo": ("MOVIL", "CODCHO", "CHOFER", "IDCHO", "CHOF", "C_CHOFER"),
    "viaje_codigo": ("VIAJ", "FACTURANRO", "CODVIAJE", "VIAJE", "IDVIAJE", "NROVIAJE"),
    "numero_factura": ("COMPROBANT", "FACTURA", "NROFACT", "NRO_FACT", "NUMERO", "NUMFAC", "COMPROB"),
}


@dataclass(frozen=True)
class DBFImportTarget:
    """Archivo DBF a procesar.

    `name` identifica el destino logico dentro del importador. `path` puede ser
    absoluto o relativo a la carpeta base indicada al crear el importador.
    """

    name: str
    path: Path


class ImportadorDBF:
    """Importador DBF manual, aislado del flujo normal del sistema.

    Esta clase queda preparada para reutilizacion futura:
    - acepta un mapa dinamico de archivos (`dbf_files`) en vez de depender de
      nombres fijos;
    - las rutas pueden ser absolutas o relativas a `carpeta`;
    - cada archivo falla de forma aislada y deja registro en `stats`/logs;
    - los campos se leen mediante aliases para tolerar DBF con nombres distintos.

    No se ejecuta automaticamente. Para usarlo en el futuro:
        python manage.py importar_dbf --carpeta imports --solo-inspeccionar
        python manage.py importar_dbf --archivo clientes=otra_carpeta/MISCLIENTES.DBF --solo-inspeccionar
        python manage.py importar_dbf --carpeta imports
    """

    def __init__(self, carpeta=".", encoding="cp850", logger=None, dbf_files=None, field_aliases=None):
        self.carpeta = Path(carpeta or ".")
        self.encoding = encoding
        self.logger = logger or LOGGER
        self.dbf_files = dict(dbf_files or DEFAULT_DBF_FILES)
        self.field_aliases = {**FIELD_ALIASES, **(field_aliases or {})}
        self.max_retries = 3
        self.stats = {
            "creados": 0,
            "actualizados": 0,
            "omitidos": 0,
            "saltados": 0,
            "errores": 0,
        }

    def importar_todo(self):
        for target_name in self.dbf_files:
            self.importar(target_name)
        return self.stats

    def inspeccionar(self):
        info = {}
        for target in self.targets():
            path = target.path
            if not path.exists():
                info[target.name] = {"path": str(path), "missing": True}
                continue
            try:
                table_info = DBFTable(path, encoding=self.encoding).inspect()
                info[target.name] = {
                    "path": table_info["path"],
                    "record_count": table_info["record_count"],
                    "fields": table_info["fields"],
                }
            except Exception as exc:
                self.stats["errores"] += 1
                self.logger.exception("%s no se pudo inspeccionar: %s", path, exc)
                info[target.name] = {"path": str(path), "error": str(exc)}
        return info

    def targets(self):
        for name, raw_path in self.dbf_files.items():
            yield DBFImportTarget(name=name, path=self.resolve_path(raw_path))

    def resolve_path(self, raw_path):
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return self.carpeta / path

    def importar(self, target_name):
        importers = {
            "clientes": self._import_cliente,
            "choferes": self._import_chofer,
            "viajes": self._import_viaje,
            "facturas": self._import_factura,
        }
        importer = importers.get(target_name)
        if importer is None:
            self.stats["omitidos"] += 1
            self.logger.warning("Destino DBF desconocido: %s. Se omite.", target_name)
            return
        return self._import_table(target_name, importer)

    def importar_clientes(self):
        return self.importar("clientes")

    def importar_choferes(self):
        return self.importar("choferes")

    def importar_viajes(self):
        return self.importar("viajes")

    def importar_facturas(self):
        return self.importar("facturas")

    def _import_table(self, key, importer):
        path = self.resolve_path(self.dbf_files[key])
        filename = path.name
        if not path.exists():
            self.stats["omitidos"] += 1
            self.logger.warning("%s no encontrado (%s)", key, path)
            return

        try:
            table = DBFTable(path, encoding=self.encoding)
            info = table.inspect()
            field_summary = ", ".join(f"{field.name}:{field.type}({field.length})" for field in info["fields"])
            self.logger.info("%s: %s registros. Campos: %s", filename, info["record_count"], field_summary)

            for row_number, record in table:
                self._import_record_with_retry(importer, record, filename, row_number)
        except Exception as exc:
            self.stats["errores"] += 1
            self.logger.exception("%s no se pudo procesar: %s", path, exc)

    def _import_record_with_retry(self, importer, record, filename, row_number):
        for attempt in range(1, self.max_retries + 1):
            try:
                created = importer(record, filename, row_number)
                if created is None:
                    self.stats["saltados"] += 1
                    return
                self.stats["creados" if created else "actualizados"] += 1
                return
            except OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < self.max_retries:
                    self.logger.warning(
                        "%s fila %s reintento %s/%s por bloqueo SQLite: %s",
                        filename,
                        row_number,
                        attempt,
                        self.max_retries,
                        exc,
                    )
                    sleep(0.25 * attempt)
                    continue
                self.stats["errores"] += 1
                self.logger.exception("%s fila %s no importada por error SQLite: %s. Datos=%s", filename, row_number, exc, record)
                return
            except Exception as exc:
                self.stats["errores"] += 1
                self.logger.exception("%s fila %s no importada: %s. Datos=%s", filename, row_number, exc, record)
                return

    def value(self, record, logical_name, *fallback_names):
        for field_name in self.field_aliases.get(logical_name, ()):
            if field_name in record:
                return record[field_name]
        for field_name in fallback_names:
            if field_name in record:
                return record[field_name]
        return None

    def text(self, record, logical_name, *fallback_names):
        return value_as_text(self.value(record, logical_name, *fallback_names))

    def _import_cliente(self, record, filename, row_number):
        if is_cliente_row_to_skip(record, self):
            self.logger.warning("%s fila %s saltada por no representar un cliente valido. Datos=%s", filename, row_number, record)
            return None

        codigo = self.text(record, "codigo", "CODIGO", "TELEF") or f"{filename}:{row_number}"
        defaults = {
            "nombre": self.text(record, "nombre", "NAME") or f"Cliente legacy {codigo}",
            "telefono": unique_text_or_none(self.value(record, "telefono", "TELEF")),
            "direccion": build_cliente_direccion(record, self),
            "observaciones": legacy_note("Importado desde CLIENTES.DBF", record),
            "activo": normalize_yes_no(self.value(record, "estado", "SUSPENDIDO")) is not True,
            "origen_legacy": filename,
            "datos_legacy": serialize_record(record),
        }
        return upsert_by_legacy(Cliente, codigo, defaults)

    def _import_chofer(self, record, filename, row_number):
        codigo = self.text(record, "codigo", "MOVIL") or f"{filename}:{row_number}"
        nombre = " ".join(
            part for part in [
                value_as_text(record.get("APELL")),
                self.text(record, "nombre", "NOMBRE"),
            ]
            if part
        )
        defaults = {
            "nombre": nombre or f"Chofer legacy {codigo}",
            "telefono": unique_text_or_none(self.value(record, "telefono", "TEL_CHOF")),
            "dni": unique_text_or_none(self.value(record, "dni", "NRODOC")),
            "registro": self.text(record, "registro", "NROREGIS"),
            "direccion": join_parts(self.value(record, "direccion", "DIRECCION"), record.get("LOCALIDAD")),
            "estado": normalize_estado_chofer(self.value(record, "estado", "ACTIVO")),
            "vehiculo": self.text(record, "vehiculo", "MARCAUT"),
            "patente": unique_text_or_none(self.value(record, "patente", "NROPAT")),
            "seguro": self.text(record, "seguro", "COMPANIA"),
            "origen_legacy": filename,
            "datos_legacy": serialize_record(record),
        }
        return upsert_by_legacy(Chofer, codigo, defaults)

    def _import_viaje(self, record, filename, row_number):
        codigo = self.text(record, "viaje_codigo", "VIAJ") or f"{filename}:{row_number}"
        cliente_codigo = self.text(record, "cliente_codigo", "TELEF")
        chofer_codigo = self.text(record, "chofer_codigo", "MOVIL")
        defaults = {
            "cliente": find_cliente(cliente_codigo),
            "chofer": find_by_legacy(Chofer, chofer_codigo),
            "fecha": parse_date(self.value(record, "fecha", "FECHA")),
            "origen": self.text(record, "origen", "DESDEORI", "DESDE"),
            "destino": self.text(record, "destino", "DESTIORI", "DESTINO"),
            "importe": importe_viaje(record),
            "estado": normalize_estado_viaje_real(record),
            "observaciones": build_viaje_observaciones(record),
            "cliente_codigo_legacy": cliente_codigo,
            "chofer_codigo_legacy": chofer_codigo,
            "origen_legacy": filename,
            "datos_legacy": serialize_record(record),
        }
        return upsert_by_legacy(Viaje, codigo, defaults)

    def _import_factura(self, record, filename, row_number):
        codigo = f"{filename}:{row_number:06d}"
        cliente_codigo = self.text(record, "cliente_codigo", "CENCOS")
        viaje_codigo = ""
        numero = self.text(record, "numero_factura", "COMPROBANT") or codigo
        defaults = {
            "cliente": find_cliente(cliente_codigo),
            "viaje": None,
            "numero": numero,
            "fecha": parse_date(self.value(record, "fecha", "FECHA")),
            "importe_total": Decimal("0.00"),
            "estado": "sin_estado",
            "observaciones": build_factura_observaciones(record),
            "cliente_codigo_legacy": cliente_codigo,
            "viaje_codigo_legacy": viaje_codigo,
            "origen_legacy": filename,
            "datos_legacy": serialize_record(record),
        }
        return upsert_by_legacy(Factura, codigo, defaults)


def pick(record, logical_name):
    for field_name in FIELD_ALIASES.get(logical_name, ()):
        if field_name in record:
            return record[field_name]
    return None


def value_as_text(value):
    if value is None:
        return ""
    return str(value).strip()


def unique_text_or_none(value):
    text = value_as_text(value)
    return text or None


def join_parts(*parts):
    return " ".join(value_as_text(part) for part in parts if value_as_text(part))


def build_cliente_direccion(record, importador=None):
    calle = importador.text(record, "direccion", "CALLE_CLI") if importador else value_as_text(record.get("CALLE_CLI"))
    numero = value_as_text(record.get("NRO_CLI"))
    piso = value_as_text(record.get("PISO"))
    dto = value_as_text(record.get("DTO"))
    localidad = value_as_text(record.get("LOCALIDAD"))
    direccion = join_parts(calle, numero, piso, dto)
    if localidad:
        return f"{direccion} - {localidad}" if direccion else localidad
    return direccion


def is_cliente_row_to_skip(record, importador=None):
    if importador:
        name = importador.text(record, "nombre", "NAME").upper()
        telefono = importador.text(record, "telefono", "TELEF")
        direccion = importador.text(record, "direccion", "CALLE_CLI")
    else:
        name = value_as_text(record.get("NAME")).upper()
        telefono = value_as_text(record.get("TELEF"))
        direccion = value_as_text(record.get("CALLE_CLI"))
    if "REGENERE INDICES" in name:
        return True
    return not any([name, telefono, direccion])


def parse_decimal(value):
    if value in (None, ""):
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    try:
        return Decimal(str(value).strip().replace(",", ".")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value

    text = str(value).strip()
    for fmt in ("%Y%m%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def normalize_yes_no(value):
    text = value_as_text(value).upper()
    if text in {"S", "Y", "T", "1", "SI", "TRUE"}:
        return True
    if text in {"N", "F", "0", "NO", "FALSE"}:
        return False
    return None


def normalize_estado_chofer(value):
    text = value_as_text(value).lower()
    if text in {"inactivo", "baja", "0", "false", "no", "n"}:
        return "inactivo"
    return "activo"


def normalize_estado_viaje_real(record):
    if normalize_yes_no(record.get("CANCELADA")) or normalize_yes_no(record.get("BORRADO")) or normalize_yes_no(record.get("SUSPENDIDA")):
        return "cancelado"
    if normalize_yes_no(record.get("LIQUIDADA")):
        return "finalizado"
    if normalize_yes_no(record.get("PENDIENTE")) or normalize_yes_no(record.get("PENDIENT")):
        return "pendiente"
    return normalize_estado_viaje(record.get("STATUS"))


def normalize_estado_viaje(value):
    text = value_as_text(value).lower()
    if text in {"pendiente", "p"}:
        return "pendiente"
    if text in {"curso", "en_curso", "en curso"}:
        return "en_curso"
    if text in {"finalizado", "cerrado", "terminado", "f"}:
        return "finalizado"
    if text in {"cancelado", "anulado", "c"}:
        return "cancelado"
    return "sin_estado"


def normalize_estado_factura(value):
    text = value_as_text(value).lower()
    if text in {"pagada", "pagado", "cobrada", "cobrado"}:
        return "pagada"
    if text in {"pendiente", "p"}:
        return "pendiente"
    if text in {"anulada", "anulado", "cancelada", "cancelado"}:
        return "anulada"
    return "sin_estado"


def importe_viaje(record):
    for field_name in ("IMPORTEORI", "VALORVIAJE", "MONTOFIJO"):
        amount = parse_decimal(record.get(field_name))
        if amount:
            return amount
    return parse_decimal(record.get("CONTADO")) + parse_decimal(record.get("CTACTE"))


def build_viaje_observaciones(record):
    parts = [
        f"Hora salida: {value_as_text(record.get('HSAL'))}" if value_as_text(record.get("HSAL")) else "",
        f"Hora puerta: {value_as_text(record.get('HPUERTA'))}" if value_as_text(record.get("HPUERTA")) else "",
        f"Pasajero: {value_as_text(record.get('PASAJ'))}" if value_as_text(record.get("PASAJ")) else "",
        f"Responsable: {value_as_text(record.get('RESPONS'))}" if value_as_text(record.get("RESPONS")) else "",
        f"Comprobante: {value_as_text(record.get('COMPROBANT'))}" if value_as_text(record.get("COMPROBANT")) else "",
        value_as_text(record.get("OBSERV")),
    ]
    detail = ". ".join(part for part in parts if part)
    base = "Importado desde VIAJES.DBF"
    return f"{base}. {detail}" if detail else legacy_note(base, record)


def build_factura_observaciones(record):
    parts = [
        f"Desde: {value_as_text(record.get('DESDE'))}" if value_as_text(record.get("DESDE")) else "",
        f"Destino: {value_as_text(record.get('DESTINO'))}" if value_as_text(record.get("DESTINO")) else "",
        f"Pasajero: {value_as_text(record.get('PASAJ'))}" if value_as_text(record.get("PASAJ")) else "",
        f"Responsable: {value_as_text(record.get('RESPONS'))}" if value_as_text(record.get("RESPONS")) else "",
        f"Centro de costo: {value_as_text(record.get('CENTROCOST'))}" if value_as_text(record.get("CENTROCOST")) else "",
        value_as_text(record.get("OBSERV")),
    ]
    detail = ". ".join(part for part in parts if part)
    base = "Importado desde FACTURAC.DBF sin importe/numero explicito en el DBF"
    return f"{base}. {detail}" if detail else legacy_note(base, record)


def serialize_record(record):
    serialized = {}
    for key, value in record.items():
        if isinstance(value, (date, Decimal)):
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized


def legacy_note(prefix, record):
    return f"{prefix}. Campos originales disponibles en datos_legacy. Campos detectados: {', '.join(record.keys())}"


def find_by_legacy(model, codigo):
    if not codigo:
        return None
    return model.objects.filter(codigo_legacy=codigo).first()


def find_cliente(codigo_o_telefono):
    if not codigo_o_telefono:
        return None
    return (
        Cliente.objects.filter(codigo_legacy=codigo_o_telefono).first()
        or Cliente.objects.filter(telefono=codigo_o_telefono).first()
    )


def upsert_by_legacy(model, codigo, defaults):
    try:
        _, created = model.objects.update_or_create(codigo_legacy=codigo, defaults=defaults)
        return created
    except IntegrityError:
        # Algunas bases viejas repiten telefonos, DNI o patentes vacios/cargados.
        # Si una restriccion heredada choca, conservamos el registro anulando esos campos.
        for field_name in ("telefono", "dni", "patente"):
            if field_name in defaults:
                defaults[field_name] = None
        _, created = model.objects.update_or_create(codigo_legacy=codigo, defaults=defaults)
        return created
