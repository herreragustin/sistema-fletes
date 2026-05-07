from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from struct import unpack


class DBFError(Exception):
    pass


@dataclass(frozen=True)
class DBFField:
    name: str
    type: str
    length: int
    decimals: int


class DBFTable:
    """
    Lector pequeno de DBF/FoxPro para migraciones puntuales futuras.

    Soporta los tipos frecuentes: texto, numericos, fechas, logicos, moneda,
    enteros y fechas-hora FoxPro. Los campos memo quedan como puntero crudo
    porque leer FPT depende de variantes del sistema anterior.

    Uso manual:
        from importadores.dbf import DBFTable
        table = DBFTable("imports/CLIENTES.DBF", encoding="cp850")
        print(table.inspect())
    """

    def __init__(self, path, encoding="cp1252"):
        self.path = Path(path)
        self.encoding = encoding
        self.fields = []
        self.record_count = 0
        self.header_length = 0
        self.record_length = 0

    def __iter__(self):
        with self.path.open("rb") as dbf_file:
            self._read_header(dbf_file)
            dbf_file.seek(self.header_length)
            for row_number in range(1, self.record_count + 1):
                raw_record = dbf_file.read(self.record_length)
                if len(raw_record) != self.record_length:
                    raise DBFError(f"Registro {row_number}: largo inesperado")
                if raw_record[:1] == b"*":
                    continue
                yield row_number, self._parse_record(raw_record[1:])

    def inspect(self):
        with self.path.open("rb") as dbf_file:
            self._read_header(dbf_file)
        return {
            "path": str(self.path),
            "record_count": self.record_count,
            "fields": self.fields,
        }

    def _read_header(self, dbf_file):
        header = dbf_file.read(32)
        if len(header) < 32:
            raise DBFError(f"{self.path.name}: cabecera DBF incompleta")

        self.record_count = unpack("<I", header[4:8])[0]
        self.header_length = unpack("<H", header[8:10])[0]
        self.record_length = unpack("<H", header[10:12])[0]
        fields = []

        while True:
            descriptor = dbf_file.read(32)
            if not descriptor:
                raise DBFError(f"{self.path.name}: terminador de campos no encontrado")
            if descriptor[0] == 0x0D:
                break

            name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore")
            field_type = chr(descriptor[11])
            length = descriptor[16]
            decimals = descriptor[17]
            fields.append(DBFField(name=name.upper(), type=field_type, length=length, decimals=decimals))

        self.fields = fields

    def _parse_record(self, payload):
        position = 0
        record = {}
        for field in self.fields:
            raw = payload[position:position + field.length]
            position += field.length
            record[field.name] = self._parse_value(field, raw)
        return record

    def _parse_value(self, field, raw):
        if field.type in {"C", "M", "G", "P"}:
            value = raw.decode(self.encoding, errors="replace").strip()
            return value or None

        if field.type == "D":
            text = raw.decode("ascii", errors="ignore").strip()
            if not text or text == "00000000":
                return None
            try:
                return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            except ValueError:
                return text

        if field.type in {"N", "F", "B", "Y"}:
            text = raw.decode("ascii", errors="ignore").strip().replace(",", ".")
            if not text:
                return None
            try:
                if field.decimals == 0 and "." not in text:
                    return int(text)
                return Decimal(text)
            except (InvalidOperation, ValueError):
                return text

        if field.type in {"I", "+"} and len(raw) == 4:
            return unpack("<i", raw)[0]

        if field.type == "L":
            text = raw[:1].decode("ascii", errors="ignore").upper()
            if text in {"Y", "T", "S"}:
                return True
            if text in {"N", "F"}:
                return False
            return None

        if field.type == "T" and len(raw) == 8:
            # FoxPro datetime: por compatibilidad guardamos el valor crudo.
            return raw.hex()

        return raw.decode(self.encoding, errors="replace").strip() or None
