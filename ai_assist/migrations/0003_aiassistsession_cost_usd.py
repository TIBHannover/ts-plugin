from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ai_assist", "0002_ai_assist_session_logs")]

    operations = [
        migrations.AddField(
            model_name="aiassistsession",
            name="cost_usd",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=20),
        ),
    ]
