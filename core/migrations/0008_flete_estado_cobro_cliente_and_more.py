from django.db import migrations, models


def inicializar_estados_financieros(apps, schema_editor):
    Flete = apps.get_model("core", "Flete")
    Cobro = apps.get_model("core", "Cobro")
    cobros_por_flete = {
        cobro.flete_id: cobro.estado
        for cobro in Cobro.objects.all().only("flete_id", "estado")
    }

    for flete in Flete.objects.all().iterator():
        cobro_estado = cobros_por_flete.get(flete.id)

        if flete.estado == "finalizado":
            if cobro_estado == "pagado" or flete.pagado:
                flete.estado_cobro_cliente = "cobrado"
            elif cobro_estado == "cancelado":
                flete.estado_cobro_cliente = "cancelado"
            else:
                flete.estado_cobro_cliente = "pendiente"
            flete.estado_pago_chofer = "pendiente"
        elif flete.estado == "cancelado":
            flete.estado_cobro_cliente = "cancelado"
            flete.estado_pago_chofer = "no_liquidable"
        else:
            flete.estado_cobro_cliente = "no_exigible"
            flete.estado_pago_chofer = "no_liquidable"

        flete.pagado = flete.estado_cobro_cliente == "cobrado"
        flete.save(update_fields=["estado_cobro_cliente", "estado_pago_chofer", "pagado"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_simplificar_estados_flete"),
    ]

    operations = [
        migrations.AddField(
            model_name="flete",
            name="estado_cobro_cliente",
            field=models.CharField(
                choices=[
                    ("no_exigible", "No exigible"),
                    ("pendiente", "Pendiente"),
                    ("cobrado", "Cobrado"),
                    ("cancelado", "Cancelado"),
                ],
                default="no_exigible",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="flete",
            name="estado_pago_chofer",
            field=models.CharField(
                choices=[
                    ("no_liquidable", "No liquidable"),
                    ("pendiente", "Pendiente"),
                    ("liquidado", "Liquidado"),
                    ("retenido", "Retenido"),
                ],
                default="no_liquidable",
                max_length=20,
            ),
        ),
        migrations.RunPython(inicializar_estados_financieros, migrations.RunPython.noop),
    ]
