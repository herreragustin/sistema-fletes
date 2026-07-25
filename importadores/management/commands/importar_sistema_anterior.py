from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from importadores.sistema_anterior import SistemaAnteriorImporter


class Command(BaseCommand):
    help = "Importa datos del sistema anterior a tablas historicas de solo consulta."

    def add_arguments(self, parser):
        parser.add_argument("carpeta", help="Ruta a la carpeta RESERVAS del sistema anterior.")
        parser.add_argument("--encoding", default="cp850", help="Encoding de los DBF/FPT. Por defecto cp850.")
        parser.add_argument("--dry-run", action="store_true", help="Lee y valida sin escribir en la base.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Reemplaza explicitamente la carga historica anterior dentro de una transaccion.",
        )

    def handle(self, *args, **options):
        carpeta = Path(options["carpeta"])
        importer = SistemaAnteriorImporter(carpeta, encoding=options["encoding"])

        try:
            paths = importer.validate()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.NOTICE(f"Carpeta validada: {carpeta}"))
        current_counts = importer.current_counts()
        self.stdout.write(self.style.NOTICE("Registros historicos actuales:"))
        for target, count in current_counts.items():
            self.stdout.write(f"  - {target}: {count}")

        if options["dry_run"]:
            _, stats = importer.dry_run(paths)
            self._print_stats(stats, dry_run=True)
            return

        try:
            _, stats = importer.import_data(paths, replace=options["replace"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self._print_stats(stats, dry_run=False)

    def _print_stats(self, stats, dry_run=False):
        modo = "Dry run" if dry_run else "Importacion"
        self.stdout.write(self.style.NOTICE(f"{modo} por destino:"))
        for target, target_stats in stats["targets"].items():
            self.stdout.write(
                f"  - {target}: "
                f"leidos={target_stats['rows_read']} "
                f"creados={target_stats['created']} "
                f"actualizados={target_stats['updated']} "
                f"omitidos={target_stats['omitted']} "
                f"errores={target_stats['errors']}"
            )

        totals = stats["totals"]
        self.stdout.write(
            self.style.SUCCESS(
                f"{modo} finalizado: "
                f"leidos={totals['rows_read']} "
                f"creados={totals['created']} "
                f"actualizados={totals['updated']} "
                f"omitidos={totals['omitted']} "
                f"errores={totals['errors']}"
            )
        )
