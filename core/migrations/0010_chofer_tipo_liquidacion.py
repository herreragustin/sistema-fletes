from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_flete_fecha_pago_chofer_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="chofer",
            name="tipo_liquidacion",
            field=models.CharField(
                choices=[
                    ("semanal", "Semanal"),
                    ("quincenal", "Quincenal"),
                    ("mensual", "Mensual"),
                ],
                default="semanal",
                max_length=20,
            ),
        ),
    ]
