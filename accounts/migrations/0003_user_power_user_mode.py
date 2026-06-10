# SFLL-117 — power_user_mode feature flag for Tweaks panel + ⌘K palette.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='power_user_mode',
            field=models.BooleanField(
                default=False,
                help_text='Enable Tweaks panel + ⌘K command palette for this user.',
            ),
        ),
    ]
