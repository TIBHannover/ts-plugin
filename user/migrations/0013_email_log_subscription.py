from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("user", "0012_email_verification")]

    operations = [
        migrations.AddField(
            model_name="emaillog",
            name="recipient_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="user.usermodel"),
        ),
        migrations.AddField(
            model_name="emaillog",
            name="ontology_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
