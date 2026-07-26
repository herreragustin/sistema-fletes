from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.db import transaction

from .dbf import DBFTable
from .models import (
    ChoferHistorico,
    ClienteHistorico,
    ReservaHistorica,
    ViajeHistorico,
)


REQUIRED_FILES = {
    "clientes": "CLIENTES.DBF",
    "choferes": "CHOFERES.DBF",
    "viajes": "VIAJES.DBF",
}

OPTIONAL_RESERVA_FILES = {
    "reservas": ["RESVIAK.DBF", "RESBAK.DBF"],
}

TIPO_PROBABLE_CHOICES = {
    "flete_utilitario": "Flete-utilitario",
    "auto_remis": "Auto-remis",
    "desconocido": "Desconocido",
}

UTILITARIO_KEYWORDS = (
    "FIORINO", "KANGOO", "KANGO", "PARTNER", "EXPRESS", "SPRINTER", "IVECO",
    "CARGO", "BENZ", "MERCEDES", "M BENZ", "M. BENZ", "AGRALE", "CAMION",
    "CAMIÓN", "DUCATO", "MASTER", "BERLINGO", "BOXER", "DAILY", "TRAFIC", "FURGON",
    "FURGÓN", "UTILITARIO", "608", "710", "915", "1215",
)

AUTO_REMIS_KEYWORDS = (
    "RENAULT 21", "RENAULT-21", "RENAULT 19", "RENAULT-19", "SIENA",
    "ESCORT", "CORSA", "VOYAGE", "SEDAN", "AUTO", "REMIS",
)

FIELD_ALIASES = {
    "codigo": ("CODIGO", "COD", "ID", "NRO", "NUMERO", "CLIENTE", "CHOFER", "VIAJE", "VIAJ", "MOVIL", "RESERVA"),
    "nombre": ("NAME", "NOMBRE", "RAZON", "RAZONSOC", "RAZON_SOC", "APELLIDO", "APELL", "NOMAPE", "DESCRIP"),
    "telefono": ("TELEF", "TELEFONO", "TEL", "TEL_CHOF", "CELULAR", "CEL", "FONO"),
    "direccion": ("CALLE_CLI", "DIRECCION", "DOMICILIO", "DOM", "DIR", "DESDE"),
    "dni": ("NRODOC", "DNI", "DOCUMENTO", "DOC", "CUIT", "CUIL"),
    "registro": ("NROREGIS", "REGISTRO", "LICENCIA", "CARNET"),
    "vehiculo": ("MARCAUT", "VEHICULO", "CAMION", "UNIDAD"),
    "patente": ("NROPAT", "PATENTE", "DOMINIO"),
    "seguro": ("COMPANIA", "SEGURO", "POLIZA"),
    "fecha": ("FECHA", "FEC", "FE_VIAJE", "FECVIAJE", "FECHA_VIA"),
    "hora": ("HORA", "HSAL", "HORA_VIA", "HORSAL", "HPUERTA"),
    "origen": ("DESDEORI", "DESDE", "ORIGEN", "CARGA", "DIR_ORIG", "REMITO"),
    "destino": ("DESTIORI", "HASTAORI", "DESTINO", "HASTA", "DESCARGA", "DIR_DEST"),
    "importe": ("IMPORTEORI", "VALORVIAJE", "CONTADO", "CTACTE", "VAL", "IMPORTE", "TOTAL", "PRECIO", "MONTO", "VALOR"),
    "estado": ("CANCELADA", "LIQUIDADA", "STATUS", "ACTIVO", "ESTADO", "SITUACION", "PENDIENTE", "RESERVA"),
    "cliente_codigo": ("TELEF", "CODCLI", "CLIENTE", "IDCLI", "CLI", "C_CLIENTE", "CENCOS"),
    "chofer_codigo": ("MOVIL", "CODCHO", "CHOFER", "IDCHO", "CHOF", "C_CHOFER"),
    "observaciones": ("OBSERV", "OBS", "OBSERVACIO", "DETALLE", "NOTA"),
}


@dataclass
class TargetSummary:
    target: str
    source_file: str
    rows_read: int = 0
    created: int = 0
    updated: int = 0
    omitted: int = 0
    errors: int = 0


class SistemaAnteriorImporter:
    def __init__(self, base_path, encoding="cp850"):
        self.base_path = Path(base_path)
        self.encoding = encoding
        self.summaries = {}
        self._used_codes = {}
        self._choferes_payload_by_code = {}

    def validate(self):
        if not self.base_path.exists() or not self.base_path.is_dir():
            raise ValueError(f"La carpeta no existe: {self.base_path}")

        missing = []
        paths = {}
        for target, filename in REQUIRED_FILES.items():
            path = self.base_path / filename
            if not path.exists():
                missing.append(filename)
            else:
                paths[target] = path

        reserva_paths = []
        for filename in OPTIONAL_RESERVA_FILES["reservas"]:
            path = self.base_path / filename
            if path.exists():
                reserva_paths.append(path)
        if not reserva_paths:
            missing.append("RESVIAK.DBF o RESBAK.DBF")

        if missing:
            raise ValueError(f"Faltan archivos requeridos: {', '.join(missing)}")

        paths["reservas"] = reserva_paths
        return paths

    def current_counts(self):
        return {
            "clientes": ClienteHistorico.objects.count(),
            "choferes": ChoferHistorico.objects.count(),
            "viajes": ViajeHistorico.objects.count(),
            "reservas": ReservaHistorica.objects.count(),
        }

    def dry_run(self, paths):
        payload = self._parse_all(paths)
        stats = self._simulate_stats(payload)
        return payload, stats

    def import_data(self, paths, replace=False):
        payload = self._parse_all(paths)
        if replace and self._has_parse_errors():
            raise ValueError(
                "La nueva carga historica tiene errores de lectura/parsing. "
                "No se reemplazo la importacion anterior para evitar dejarla incompleta. "
                "Ejecute primero con --dry-run y revise el resumen."
            )
        if replace:
            stats = self._replace_all(payload)
        else:
            stats = self._upsert_all(payload)
        return payload, stats

    def _parse_all(self, paths):
        self.summaries = {}
        self._used_codes = defaultdict(set)
        clientes = self._parse_clientes(paths["clientes"])
        choferes = self._parse_choferes(paths["choferes"])
        self._choferes_payload_by_code = {row["codigo_legacy"]: row for row in choferes}
        payload = {
            "clientes": clientes,
            "choferes": choferes,
            "viajes": self._parse_viajes(paths["viajes"]),
            "reservas": self._parse_reservas(paths["reservas"]),
        }
        return payload

    def _simulate_stats(self, payload):
        stats = {"targets": {}, "totals": defaultdict(int)}
        existing_codes = {
            "clientes": set(ClienteHistorico.objects.values_list("codigo_legacy", flat=True)),
            "choferes": set(ChoferHistorico.objects.values_list("codigo_legacy", flat=True)),
            "viajes": set(ViajeHistorico.objects.values_list("codigo_legacy", flat=True)),
            "reservas": set(ReservaHistorica.objects.values_list("codigo_legacy", flat=True)),
        }

        for target, rows in payload.items():
            created = 0
            updated = 0
            for row in rows:
                if row["codigo_legacy"] in existing_codes[target]:
                    updated += 1
                else:
                    created += 1
            stats["targets"][target] = self._target_stats(
                target=target,
                created=created,
                updated=updated,
            )
            self._accumulate_totals(stats["totals"], stats["targets"][target])
        return stats

    def _replace_all(self, payload):
        stats = {"targets": {}, "totals": defaultdict(int)}
        with transaction.atomic():
            ReservaHistorica.objects.all().delete()
            ViajeHistorico.objects.all().delete()
            ChoferHistorico.objects.all().delete()
            ClienteHistorico.objects.all().delete()

            clientes = [ClienteHistorico(**row) for row in payload["clientes"]]
            choferes = [ChoferHistorico(**row) for row in payload["choferes"]]
            ClienteHistorico.objects.bulk_create(clientes, batch_size=500)
            ChoferHistorico.objects.bulk_create(choferes, batch_size=500)

            clientes_map = {obj.codigo_legacy: obj for obj in ClienteHistorico.objects.all()}
            choferes_map = {obj.codigo_legacy: obj for obj in ChoferHistorico.objects.all()}

            viajes = []
            for row in payload["viajes"]:
                row = row.copy()
                row["cliente"] = clientes_map.get(row.pop("cliente_codigo_legacy_ref"))
                row["chofer"] = choferes_map.get(row.pop("chofer_codigo_legacy_ref"))
                viajes.append(ViajeHistorico(**row))
            ViajeHistorico.objects.bulk_create(viajes, batch_size=500)

            reservas = []
            for row in payload["reservas"]:
                row = row.copy()
                row["cliente"] = clientes_map.get(row.pop("cliente_codigo_legacy_ref"))
                row["chofer"] = choferes_map.get(row.pop("chofer_codigo_legacy_ref"))
                reservas.append(ReservaHistorica(**row))
            ReservaHistorica.objects.bulk_create(reservas, batch_size=500)

        for target in ("clientes", "choferes", "viajes", "reservas"):
            count = len(payload[target])
            stats["targets"][target] = self._target_stats(
                target=target,
                created=count,
                updated=0,
            )
            self._accumulate_totals(stats["totals"], stats["targets"][target])
        return stats

    def _upsert_all(self, payload):
        stats = {"targets": {}, "totals": defaultdict(int)}
        clientes_map = {}
        choferes_map = {}

        cliente_created = cliente_updated = 0
        for row in payload["clientes"]:
            obj, created = ClienteHistorico.objects.update_or_create(
                codigo_legacy=row["codigo_legacy"],
                defaults=row,
            )
            clientes_map[obj.codigo_legacy] = obj
            cliente_created += int(created)
            cliente_updated += int(not created)
        stats["targets"]["clientes"] = self._target_stats(
            target="clientes",
            created=cliente_created,
            updated=cliente_updated,
        )

        chofer_created = chofer_updated = 0
        for row in payload["choferes"]:
            obj, created = ChoferHistorico.objects.update_or_create(
                codigo_legacy=row["codigo_legacy"],
                defaults=row,
            )
            choferes_map[obj.codigo_legacy] = obj
            chofer_created += int(created)
            chofer_updated += int(not created)
        stats["targets"]["choferes"] = self._target_stats(
            target="choferes",
            created=chofer_created,
            updated=chofer_updated,
        )

        viaje_created = viaje_updated = 0
        for row in payload["viajes"]:
            defaults = row.copy()
            defaults["cliente"] = clientes_map.get(defaults.pop("cliente_codigo_legacy_ref"))
            defaults["chofer"] = choferes_map.get(defaults.pop("chofer_codigo_legacy_ref"))
            _, created = ViajeHistorico.objects.update_or_create(
                codigo_legacy=row["codigo_legacy"],
                defaults=defaults,
            )
            viaje_created += int(created)
            viaje_updated += int(not created)
        stats["targets"]["viajes"] = self._target_stats(
            target="viajes",
            created=viaje_created,
            updated=viaje_updated,
        )

        reserva_created = reserva_updated = 0
        for row in payload["reservas"]:
            defaults = row.copy()
            defaults["cliente"] = clientes_map.get(defaults.pop("cliente_codigo_legacy_ref"))
            defaults["chofer"] = choferes_map.get(defaults.pop("chofer_codigo_legacy_ref"))
            _, created = ReservaHistorica.objects.update_or_create(
                codigo_legacy=row["codigo_legacy"],
                defaults=defaults,
            )
            reserva_created += int(created)
            reserva_updated += int(not created)
        stats["targets"]["reservas"] = self._target_stats(
            target="reservas",
            created=reserva_created,
            updated=reserva_updated,
        )

        for target_stats in stats["targets"].values():
            self._accumulate_totals(stats["totals"], target_stats)
        return stats

    def _target_stats(self, target, created, updated):
        summary = self.summaries.get(target)
        return {
            "rows_read": summary.rows_read if summary else created + updated,
            "created": created,
            "updated": updated,
            "omitted": summary.omitted if summary else 0,
            "errors": summary.errors if summary else 0,
        }

    def _accumulate_totals(self, totals, target_stats):
        for key, value in target_stats.items():
            totals[key] += value

    def _has_parse_errors(self):
        return any(summary.errors for summary in self.summaries.values())

    def _new_summary(self, target, source_file):
        summary = TargetSummary(target=target, source_file=source_file)
        self.summaries[target] = summary
        return summary

    def _parse_clientes(self, path):
        rows = []
        summary = self._new_summary("clientes", path.name)
        for index, record in DBFTable(path, encoding=self.encoding):
            summary.rows_read += 1
            try:
                if self._skip_cliente(record):
                    summary.omitted += 1
                    continue
                codigo_base = self._text(record, "codigo", "CODIGO", "TELEF") or f"{path.name}:{index}"
                codigo = self._unique_codigo("clientes", codigo_base, path.name, index)
                rows.append({
                    "codigo_legacy": codigo,
                    "nombre": self._text(record, "nombre", "NAME") or f"Cliente legacy {codigo}",
                    "telefono": self._text(record, "telefono", "TELEF"),
                    "direccion": self._build_cliente_direccion(record),
                    "activo": self._normalize_yes_no(record.get("SUSPENDIDO")) is not True,
                    "observaciones": self._text(record, "observaciones", "OBSERV") or "",
                    "origen_legacy": path.name,
                    "datos_legacy": self._serialize_record(record),
                })
            except Exception:
                summary.errors += 1
        return rows

    def _parse_choferes(self, path):
        rows = []
        summary = self._new_summary("choferes", path.name)
        for index, record in DBFTable(path, encoding=self.encoding):
            summary.rows_read += 1
            try:
                codigo_base = self._text(record, "codigo", "MOVIL") or f"{path.name}:{index}"
                codigo = self._unique_codigo("choferes", codigo_base, path.name, index)
                nombre = self._build_chofer_nombre(record)
                descripcion_vehiculo = self._build_descripcion_vehiculo(record)
                patente = self._text(record, "patente", "NROPAT")
                tipo_probable, motivo_clasificacion = clasificar_tipo_probable(
                    texto_vehiculo=descripcion_vehiculo,
                    texto_observaciones=self._text(record, "observaciones", "OBSERV", "OBSERVAC"),
                )
                rows.append({
                    "codigo_legacy": codigo,
                    "nombre": nombre or f"Chofer legacy {codigo}",
                    "telefono": self._text(record, "telefono", "TEL_CHOF"),
                    "dni": self._text(record, "dni", "NRODOC"),
                    "registro": self._text(record, "registro", "NROREGIS"),
                    "direccion": self._join_parts(record.get("DIRECCION"), record.get("LOCALIDAD")),
                    "estado": self._normalize_estado_chofer(record.get("ACTIVO")),
                    "vehiculo": self._text(record, "vehiculo", "MARCAUT"),
                    "patente": patente,
                    "descripcion_vehiculo": descripcion_vehiculo,
                    "patente_legacy": patente,
                    "tipo_vehiculo_legacy": self._text(record, "TIPOVEHIC", "TIPOVEHIC"),
                    "tipo_probable": tipo_probable,
                    "motivo_clasificacion": motivo_clasificacion,
                    "seguro": self._text(record, "seguro", "COMPANIA"),
                    "observaciones": self._text(record, "observaciones", "OBSERV") or "",
                    "origen_legacy": path.name,
                    "datos_legacy": self._serialize_record(record),
                })
            except Exception:
                summary.errors += 1
        return rows

    def _parse_viajes(self, path):
        rows = []
        summary = self._new_summary("viajes", path.name)
        for index, record in DBFTable(path, encoding=self.encoding):
            summary.rows_read += 1
            try:
                codigo_base = self._text(record, "codigo", "VIAJ") or f"{path.name}:{index}"
                codigo = self._unique_codigo("viajes", codigo_base, path.name, index)
                cliente_codigo = self._text(record, "cliente_codigo", "TELEF")
                chofer_codigo = self._text(record, "chofer_codigo", "MOVIL")
                usuario_carga = self._resolve_usuario_carga_viaje(record)
                clasificacion = self._clasificacion_desde_chofer_o_registro(
                    chofer_codigo=chofer_codigo,
                    record=record,
                    usuario_carga=usuario_carga,
                )
                rows.append({
                    "codigo_legacy": codigo,
                    "cliente_codigo_legacy": cliente_codigo or "",
                    "chofer_codigo_legacy": chofer_codigo or "",
                    "cliente_codigo_legacy_ref": cliente_codigo,
                    "chofer_codigo_legacy_ref": chofer_codigo,
                    "fecha": self._parse_date(self._value(record, "fecha", "FECHA")),
                    "hora": self._parse_time(self._value(record, "hora", "HSAL", "HPUERTA")),
                    "origen": self._text(record, "origen", "DESDEORI", "DESDE"),
                    "destino": self._text(record, "destino", "DESTIORI", "DESTINO"),
                    "importe": self._importe(record),
                    "estado": self._normalize_estado_viaje(record),
                    "usuario_carga": usuario_carga,
                    "tipo_probable": clasificacion["tipo_probable"],
                    "motivo_clasificacion": clasificacion["motivo_clasificacion"],
                    "vehiculo_chofer": clasificacion["vehiculo_chofer"],
                    "observaciones": self._build_observaciones(record),
                    "origen_legacy": path.name,
                    "datos_legacy": self._serialize_record(record),
                })
            except Exception:
                summary.errors += 1
        return rows

    def _parse_reservas(self, paths):
        rows = []
        summary = self._new_summary("reservas", ", ".join(path.name for path in paths))
        for path in paths:
            for index, record in DBFTable(path, encoding=self.encoding):
                summary.rows_read += 1
                try:
                    codigo_base = self._text(record, "codigo", "VIAJ", "RESERVA", "CODIGO") or f"{path.name}:{index}"
                    codigo = self._unique_codigo("reservas", f"{path.stem}:{codigo_base}", path.name, index)
                    cliente_codigo = self._text(record, "cliente_codigo", "TELEF", "CLIENTE")
                    chofer_codigo = self._text(record, "chofer_codigo", "MOVIL", "CHOFER")
                    usuario_carga = self._resolve_usuario_carga_reserva(record)
                    clasificacion = self._clasificacion_desde_chofer_o_registro(
                        chofer_codigo=chofer_codigo,
                        record=record,
                        usuario_carga=usuario_carga,
                    )
                    rows.append({
                        "codigo_legacy": codigo,
                        "cliente_codigo_legacy": cliente_codigo or "",
                        "chofer_codigo_legacy": chofer_codigo or "",
                        "cliente_codigo_legacy_ref": cliente_codigo,
                        "chofer_codigo_legacy_ref": chofer_codigo,
                        "fecha": self._parse_date(self._value(record, "fecha", "FECHA")),
                        "hora": self._parse_time(self._value(record, "hora", "HSAL", "HPUERTA")),
                        "origen": self._text(record, "origen", "DESDEORI", "DESDE"),
                        "destino": self._text(record, "destino", "DESTIORI", "DESTINO"),
                        "importe": self._importe(record),
                        "estado": self._normalize_estado_reserva(record),
                        "usuario_carga": usuario_carga,
                        "tipo_probable": clasificacion["tipo_probable"],
                        "motivo_clasificacion": clasificacion["motivo_clasificacion"],
                        "vehiculo_chofer": clasificacion["vehiculo_chofer"],
                        "observaciones": self._build_observaciones(record),
                        "origen_legacy": path.name,
                        "datos_legacy": self._serialize_record(record),
                    })
                except Exception:
                    summary.errors += 1
        return rows

    def _value(self, record, logical_name, *fallback_names):
        for field_name in FIELD_ALIASES.get(logical_name, ()):
            if field_name in record:
                value = record[field_name]
                if self._has_useful_value(value):
                    return value
        for field_name in fallback_names:
            if field_name in record:
                value = record[field_name]
                if self._has_useful_value(value):
                    return value
        return None

    def _text(self, record, logical_name, *fallback_names):
        value = self._value(record, logical_name, *fallback_names)
        return self._value_as_text(value)

    def _has_useful_value(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, bytes):
            return bool(value.strip(b" \x00"))
        return True

    def _value_as_text(self, value):
        if value is None:
            return ""
        return str(value).strip()

    def _unique_codigo(self, target, codigo_base, source_name, index):
        codigo_base = self._value_as_text(codigo_base) or f"{source_name}:{index}"
        used = self._used_codes[target]
        if codigo_base not in used:
            used.add(codigo_base)
            return codigo_base

        codigo = f"{codigo_base}@{source_name}:{index}"
        while codigo in used:
            codigo = f"{codigo}@dup"
        used.add(codigo)
        return codigo

    def _join_parts(self, *parts):
        return " ".join(self._value_as_text(part) for part in parts if self._value_as_text(part))

    def _skip_cliente(self, record):
        name = self._text(record, "nombre", "NAME").upper()
        telefono = self._text(record, "telefono", "TELEF")
        direccion = self._text(record, "direccion", "CALLE_CLI")
        if "REGENERE INDICES" in name:
            return True
        return not any([name, telefono, direccion])

    def _build_cliente_direccion(self, record):
        calle = self._text(record, "direccion", "CALLE_CLI")
        numero = self._value_as_text(record.get("NRO_CLI"))
        piso = self._value_as_text(record.get("PISO"))
        dto = self._value_as_text(record.get("DTO"))
        localidad = self._value_as_text(record.get("LOCALIDAD"))
        direccion = self._join_parts(calle, numero, piso, dto)
        return f"{direccion} - {localidad}" if direccion and localidad else (direccion or localidad)

    def _build_chofer_nombre(self, record):
        apellido = self._value_as_text(record.get("APELL"))
        nombre = self._value_as_text(record.get("NOMBRE"))

        if nombre:
            nombre = self._clean_chofer_nombre_noise(
                nombre=nombre,
                patente=self._value_as_text(record.get("NROPAT")),
                referencia=self._value_as_text(record.get("REFEREN")),
            )

        if nombre and apellido:
            return self._join_parts(nombre, apellido)
        return nombre or apellido

    def _clean_chofer_nombre_noise(self, nombre, patente="", referencia=""):
        patente_normalizada = self._normalize_compact_token(patente)
        tokens = [token for token in nombre.split() if token]

        cleaned_tokens = []
        for token in tokens:
            token_normalizado = self._normalize_compact_token(token)
            if patente_normalizada and token_normalizado == patente_normalizada:
                continue
            cleaned_tokens.append(token)

        if referencia:
            referencia_normalizada = self._normalize_compact_token(referencia.replace("DOMINIO", " "))
            if referencia_normalizada:
                cleaned_tokens = [
                    token for token in cleaned_tokens
                    if self._normalize_compact_token(token) != referencia_normalizada
                ]

        return " ".join(cleaned_tokens).strip()

    def _build_descripcion_vehiculo(self, record):
        return self._join_parts(
            record.get("MARCAUT"),
            record.get("REFEREN"),
            record.get("TIPOVEHIC"),
            record.get("OBSERVAC"),
        )

    def _resolve_usuario_carga_viaje(self, record):
        return self._first_text(record, "USU", "MODIFIPOR", "RECIBIO", "DESPACHO", "MODIFICO", "RESERVO", "ANULO")

    def _resolve_usuario_carga_reserva(self, record):
        return self._first_text(record, "RESERVO", "USU", "MODIFIPOR", "RECIBIO", "DESPACHO", "MODIFICO", "ANULO")

    def _first_text(self, record, *field_names):
        for field_name in field_names:
            value = self._value_as_text(record.get(field_name))
            if value:
                return value
        return ""

    def _clasificacion_desde_chofer_o_registro(self, chofer_codigo, record, usuario_carga=""):
        chofer = self._choferes_payload_by_code.get(chofer_codigo or "")
        if chofer:
            motivo = chofer.get("motivo_clasificacion", "")
            if motivo:
                motivo = f"{motivo} (chofer {chofer.get('codigo_legacy')})"
            return {
                "tipo_probable": chofer.get("tipo_probable", "desconocido"),
                "motivo_clasificacion": motivo,
                "vehiculo_chofer": chofer.get("descripcion_vehiculo") or chofer.get("vehiculo", ""),
            }

        texto_vehiculo = self._join_parts(
            record.get("TIPOVEHIC"),
            record.get("MOVIL"),
            record.get("REFEREN"),
        )
        texto_observaciones = self._join_parts(record.get("OBSERV"), record.get("OBSERVAC"))
        tipo_probable, motivo_clasificacion = clasificar_tipo_probable(
            texto_vehiculo=texto_vehiculo,
            texto_observaciones=texto_observaciones,
            usuario=usuario_carga,
        )
        return {
            "tipo_probable": tipo_probable,
            "motivo_clasificacion": motivo_clasificacion,
            "vehiculo_chofer": self._value_as_text(texto_vehiculo),
        }

    def _normalize_compact_token(self, value):
        text = self._value_as_text(value).upper()
        return "".join(ch for ch in text if ch.isalnum())

    def _parse_date(self, value):
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

    def _parse_time(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, time):
            return value
        text = str(value).strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        candidates = [text]
        if len(digits) == 4:
            candidates.append(f"{digits[:2]}:{digits[2:]}")
        if len(digits) == 6:
            candidates.append(f"{digits[:2]}:{digits[2:4]}:{digits[4:]}")
        for candidate in candidates:
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    return datetime.strptime(candidate, fmt).time()
                except ValueError:
                    pass
        return None

    def _parse_decimal(self, value):
        if value in (None, ""):
            return Decimal("0.00")
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        try:
            return Decimal(str(value).strip().replace(",", ".")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    def _importe(self, record):
        for field_name in ("IMPORTEORI", "VALORVIAJE", "MONTOFIJO"):
            amount = self._parse_decimal(record.get(field_name))
            if amount:
                return amount
        return self._parse_decimal(record.get("CONTADO")) + self._parse_decimal(record.get("CTACTE"))

    def _normalize_yes_no(self, value):
        text = self._value_as_text(value).upper()
        if text in {"S", "Y", "T", "1", "SI", "TRUE"}:
            return True
        if text in {"N", "F", "0", "NO", "FALSE"}:
            return False
        return None

    def _normalize_estado_chofer(self, value):
        text = self._value_as_text(value).lower()
        if text in {"inactivo", "baja", "0", "false", "no", "n"}:
            return "inactivo"
        return "activo"

    def _normalize_estado_viaje(self, record):
        if self._normalize_yes_no(record.get("CANCELADA")) or self._normalize_yes_no(record.get("BORRADO")) or self._normalize_yes_no(record.get("SUSPENDIDA")):
            return "cancelado"
        if self._normalize_yes_no(record.get("LIQUIDADA")):
            return "finalizado"
        if self._normalize_yes_no(record.get("PENDIENTE")) or self._normalize_yes_no(record.get("PENDIENT")):
            return "pendiente"

        text = self._value_as_text(record.get("STATUS")).lower()
        if text in {"pendiente", "p", "reserva"}:
            return "pendiente"
        if text in {"curso", "en_curso", "en curso"}:
            return "en_curso"
        if text in {"finalizado", "cerrado", "terminado", "f"}:
            return "finalizado"
        if text in {"cancelado", "anulado", "c"}:
            return "cancelado"
        return "sin_estado"

    def _normalize_estado_reserva(self, record):
        estado = self._normalize_estado_viaje(record)
        if estado == "sin_estado":
            return "reserva"
        return estado

    def _build_observaciones(self, record):
        parts = [
            f"Hora salida: {self._value_as_text(record.get('HSAL'))}" if self._value_as_text(record.get("HSAL")) else "",
            f"Hora puerta: {self._value_as_text(record.get('HPUERTA'))}" if self._value_as_text(record.get("HPUERTA")) else "",
            f"Pasajero: {self._value_as_text(record.get('PASAJ'))}" if self._value_as_text(record.get("PASAJ")) else "",
            f"Responsable: {self._value_as_text(record.get('RESPONS'))}" if self._value_as_text(record.get("RESPONS")) else "",
            self._text(record, "observaciones", "OBSERV"),
        ]
        return ". ".join(part for part in parts if part)

    def _serialize_record(self, record):
        serialized = {}
        for key, value in record.items():
            if isinstance(value, (date, datetime, time, Decimal, bytes)):
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized


def clasificar_tipo_probable(texto_vehiculo="", texto_observaciones="", usuario=None):
    fuentes = []
    if texto_vehiculo:
        fuentes.append(("Vehiculo", str(texto_vehiculo)))
    if texto_observaciones:
        fuentes.append(("Observacion", str(texto_observaciones)))

    for origen, texto in fuentes:
        texto_mayus = texto.upper()
        for keyword in UTILITARIO_KEYWORDS:
            if keyword in texto_mayus:
                return "flete_utilitario", f"{origen} contiene {keyword}"
        for keyword in AUTO_REMIS_KEYWORDS:
            if keyword in texto_mayus:
                return "auto_remis", f"{origen} contiene {keyword}"

    usuario_texto = (usuario or "").strip().upper()
    if usuario_texto in {"DANIELA", "GASTON"}:
        return "desconocido", "Usuario de carga relevante, pero sin vehiculo suficiente para clasificar"

    return "desconocido", "Sin datos suficientes para clasificar"
