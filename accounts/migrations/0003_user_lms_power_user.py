from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="lms_power_user",
            field=models.BooleanField(
                default=False,
                help_text="Enables the tweaks panel and ⌘K command palette.",
            ),
        ),
    ]
