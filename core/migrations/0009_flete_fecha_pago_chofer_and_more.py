from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_flete_estado_cobro_cliente_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="flete",
            name="fecha_pago_chofer",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="flete",
            name="observaciones_pago_chofer",
            field=models.TextField(blank=True, null=True),
        ),
    ]
