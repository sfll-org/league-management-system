# Generated for SFLL-94: Pacific Player Detail (Phase 4)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("players", "0002_timezone_default_pacific"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerseason",
            name="jersey_number",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
