import logging
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.core.management.base import BaseCommand, CommandError

from importadores.importador_dbf import ImportadorDBF


class Command(BaseCommand):
    help = (
        "Importador legacy manual. Permite inspeccionar o importar DBF con "
        "rutas configurables; no se ejecuta automaticamente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--carpeta",
            default=str(settings.BASE_DIR / "imports"),
            help="Carpeta base para rutas relativas. Por defecto usa BASE_DIR/imports.",
        )
        parser.add_argument(
            "--archivo",
            action="append",
            default=[],
            metavar="DESTINO=RUTA",
            help=(
                "Ruta dinamica para un DBF. Puede repetirse. Destinos soportados: "
                "clientes, choferes, viajes, facturas. Ejemplo: "
                "--archivo clientes=C:/datos/MISCLIENTES.DBF"
            ),
        )
        parser.add_argument(
            "--encoding",
            default="cp850",
            help="Encoding de textos DBF. Por defecto cp850 para FoxPro/DOS; probar cp1252 si los textos salen mal.",
        )
        parser.add_argument(
            "--solo-inspeccionar",
            action="store_true",
            help="Muestra campos detectados sin importar datos.",
        )
        parser.add_argument(
            "--log",
            default="importacion_dbf.log",
            help="Archivo de log relativo a la carpeta del proyecto.",
        )

    def handle(self, *args, **options):
        log_path = Path(settings.BASE_DIR) / options["log"]
        logger = logging.getLogger("importadores.dbf")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path) for handler in logger.handlers):
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)

        carpeta = Path(options["carpeta"])
        dbf_files = self._build_dbf_files(options["archivo"])
        importador = ImportadorDBF(
            carpeta=carpeta,
            encoding=options["encoding"],
            logger=logger,
            dbf_files=dbf_files,
        )

        self.stdout.write(self.style.NOTICE(f"Carpeta DBF: {carpeta}"))
        if options["archivo"]:
            self.stdout.write(self.style.NOTICE("Rutas DBF indicadas manualmente:"))
            for name, path in dbf_files.items():
                self.stdout.write(f"  {name}: {path}")
        self.stdout.write(self.style.NOTICE(f"Log: {log_path}"))

        inspeccion = importador.inspeccionar()
        for nombre, info in inspeccion.items():
            if info.get("missing"):
                self.stdout.write(self.style.WARNING(f"{nombre}: no encontrado ({info['path']})"))
                logger.warning("%s no encontrado (%s)", nombre, info["path"])
                continue
            if info.get("error"):
                self.stdout.write(self.style.ERROR(f"{nombre}: error al inspeccionar ({info['error']})"))
                continue
            fields = ", ".join(
                f"{field.name}:{field.type}({field.length})"
                for field in info["fields"]
            )
            self.stdout.write(f"{nombre}: {info['record_count']} registros | {fields}")
            logger.info("%s: %s registros | %s", nombre, info["record_count"], fields)

        if options["solo_inspeccionar"]:
            self.stdout.write(self.style.SUCCESS("Inspeccion finalizada. No se importaron datos."))
            return

        self._prepare_sqlite()
        stats = importador.importar_todo()
        logger.info(
            "Importacion finalizada: %s creados, %s actualizados, %s archivos omitidos, %s filas saltadas, %s errores.",
            stats["creados"],
            stats["actualizados"],
            stats["omitidos"],
            stats["saltados"],
            stats["errores"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Importacion finalizada: "
                f"{stats['creados']} creados, "
                f"{stats['actualizados']} actualizados, "
                f"{stats['omitidos']} archivos omitidos, "
                f"{stats['saltados']} filas saltadas, "
                f"{stats['errores']} errores."
            )
        )

    def _prepare_sqlite(self):
        if connection.vendor != "sqlite":
            return
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout = 10000")

    def _build_dbf_files(self, archivo_options):
        if not archivo_options:
            return None

        dbf_files = {}
        for raw_value in archivo_options:
            if "=" not in raw_value:
                raise CommandError("--archivo debe tener formato DESTINO=RUTA")
            name, raw_path = raw_value.split("=", 1)
            name = name.strip().lower()
            raw_path = raw_path.strip()
            if not name or not raw_path:
                raise CommandError("--archivo debe incluir destino y ruta")
            dbf_files[name] = raw_path
        return dbf_files
