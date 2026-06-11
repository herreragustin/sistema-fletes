from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from core.models import Cliente, Chofer, Cobro, Flete


CLIENTES_GENERICOS = {
    "Cliente Particular 1",
    "Cliente Particular 2",
    "Comercio Centro",
    "Deposito Norte",
    "Empresa Sur",
}


def clientes_demo_qs():
    return Cliente.objects.filter(
        Q(nombre__icontains="demo") | Q(nombre__in=CLIENTES_GENERICOS)
    )


def choferes_demo_qs():
    return Chofer.objects.filter(
        Q(nombre__icontains="demo") | Q(nombre__icontains="generico")
    )


class Command(BaseCommand):
    help = "Limpia datos demo y operativos de prueba del sistema."

    def handle(self, *args, **options):
        clientes_demo = list(clientes_demo_qs().values_list("id", "nombre"))
        choferes_demo = list(choferes_demo_qs().values_list("id", "nombre"))
        total_fletes = Flete.objects.count()
        total_cobros = Cobro.objects.count()

        self.stdout.write("Se va a ejecutar la limpieza total operativa.")
        self.stdout.write(f"- Cobros a borrar: {total_cobros}")
        self.stdout.write(f"- Fletes a borrar: {total_fletes}")
        self.stdout.write(f"- Clientes demo/genericos a borrar: {len(clientes_demo)}")
        self.stdout.write(f"- Choferes demo/genericos a borrar: {len(choferes_demo)}")

        if clientes_demo:
            self.stdout.write("Clientes demo/genericos detectados:")
            for _, nombre in clientes_demo:
                self.stdout.write(f"  - {nombre}")

        if choferes_demo:
            self.stdout.write("Choferes demo/genericos detectados:")
            for _, nombre in choferes_demo:
                self.stdout.write(f"  - {nombre}")

        confirmacion = input("Escribi LIMPIAR para continuar: ").strip()
        if confirmacion != "LIMPIAR":
            self.stdout.write(self.style.WARNING("Limpieza cancelada."))
            return

        with transaction.atomic():
            cobros_borrados, _ = Cobro.objects.all().delete()
            fletes_borrados, _ = Flete.objects.all().delete()
            clientes_borrados, _ = clientes_demo_qs().delete()
            choferes_borrados, _ = choferes_demo_qs().delete()

        self.stdout.write(self.style.SUCCESS("Limpieza completada correctamente."))
        self.stdout.write(f"Cobros borrados: {cobros_borrados}")
        self.stdout.write(f"Fletes borrados: {fletes_borrados}")
        self.stdout.write(f"Clientes borrados: {clientes_borrados}")
        self.stdout.write(f"Choferes borrados: {choferes_borrados}")
