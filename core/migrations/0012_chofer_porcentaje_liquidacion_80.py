from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def actualizar_porcentaje_estandar(apps, schema_editor):
    Chofer = apps.get_model("core", "Chofer")
    Chofer.objects.filter(porcentaje_liquidacion=60).update(porcentaje_liquidacion=80)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_chofer_porcentaje_liquidacion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chofer",
            name="porcentaje_liquidacion",
            field=models.PositiveSmallIntegerField(
                default=80,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
                verbose_name="Porcentaje de liquidacion",
            ),
        ),
        migrations.RunPython(actualizar_porcentaje_estandar, migrations.RunPython.noop),
    ]
