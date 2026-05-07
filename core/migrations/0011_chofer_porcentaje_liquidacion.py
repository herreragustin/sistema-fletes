from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_chofer_tipo_liquidacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="chofer",
            name="porcentaje_liquidacion",
            field=models.PositiveSmallIntegerField(
                default=60,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
                verbose_name="Porcentaje de liquidacion",
            ),
        ),
    ]
