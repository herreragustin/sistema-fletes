from django.db import migrations, models


def convertir_asignados_a_pendiente(apps, schema_editor):
    Flete = apps.get_model("core", "Flete")
    Flete.objects.filter(estado="asignado").update(estado="pendiente")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_flete_fecha_hora_en_curso_and_more"),
    ]

    operations = [
        migrations.RunPython(
            convertir_asignados_a_pendiente,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="flete",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("en_curso", "En curso"),
                    ("finalizado", "Finalizado"),
                    ("cancelado", "Cancelado"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
    ]
