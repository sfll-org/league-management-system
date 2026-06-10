from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("draft", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="draftsession",
            name="snake_draft",
            field=models.BooleanField(
                default=True,
                help_text="If true, pick order reverses each round (snake draft).",
            ),
        ),
        migrations.AddField(
            model_name="draftsession",
            name="team_order",
            field=models.JSONField(
                default=list,
                blank=True,
                help_text="Ordered list of TeamSeason PKs defining pick order.",
            ),
        ),
    ]
