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
    enteros y fechas-hora FoxPro. Intenta resolver campos memo usando el
    archivo .FPT asociado cuando existe.

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
        self.memo_path = self.path.with_suffix(".FPT")
        self.memo_block_size = 512
        self._memo_file = None

    def __iter__(self):
        with self.path.open("rb") as dbf_file:
            self._read_header(dbf_file)
            with self._open_memo_file():
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
        if field.type in {"M", "G", "P"}:
            return self._parse_memo_value(raw)

        if field.type == "C":
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

    def _open_memo_file(self):
        class _MemoContext:
            def __init__(self, table):
                self.table = table

            def __enter__(self):
                self.table._memo_file = None
                if not self.table.memo_path.exists():
                    return None

                self.table._memo_file = self.table.memo_path.open("rb")
                header = self.table._memo_file.read(8)
                if len(header) >= 8:
                    block_size = int.from_bytes(header[6:8], byteorder="big", signed=False)
                    if block_size:
                        self.table.memo_block_size = block_size
                return self.table._memo_file

            def __exit__(self, exc_type, exc, tb):
                if self.table._memo_file is not None:
                    self.table._memo_file.close()
                self.table._memo_file = None
                return False

        return _MemoContext(self)

    def _parse_memo_value(self, raw):
        if self._memo_file is None:
            value = raw.decode(self.encoding, errors="replace").strip()
            return value or None

        pointer = self._memo_pointer(raw)
        if not pointer:
            return None

        try:
            self._memo_file.seek(pointer * self.memo_block_size)
            block_header = self._memo_file.read(8)
            if len(block_header) < 8:
                return None
            length = int.from_bytes(block_header[4:8], byteorder="big", signed=False)
            payload = self._memo_file.read(length)
            if not payload:
                return None
            return payload.rstrip(b"\x00\x1a").decode(self.encoding, errors="replace").strip() or None
        except OSError as exc:
            raise DBFError(f"{self.memo_path.name}: no se pudo leer memo FPT ({exc})") from exc

    def _memo_pointer(self, raw):
        text = raw.decode("ascii", errors="ignore").strip().strip("\x00")
        if text.isdigit():
            return int(text)
        if len(raw) >= 4:
            return int.from_bytes(raw[:4], byteorder="little", signed=False)
        return 0
