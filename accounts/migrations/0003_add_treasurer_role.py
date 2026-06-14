from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userrole',
            name='role',
            field=models.CharField(
                choices=[
                    ('cto', 'CTO / Admin'),
                    ('ses_manager', 'SES Manager'),
                    ('vp_player_agents', 'VP of Player Agents'),
                    ('president', 'President'),
                    ('player_agent', 'Player Agent'),
                    ('head_coach', 'Head Coach'),
                    ('assistant_coach', 'Assistant Coach'),
                    ('front_desk', 'Front Desk'),
                    ('comms_editor', 'Comms Editor'),
                    ('treasurer', 'Treasurer'),
                ],
                max_length=30,
            ),
        ),
    ]
