from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("user", "0011_usermodel_email")]

    operations = [
        migrations.AddField(
            model_name="usermodel",
            name="email_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usermodel",
            name="email_verification_token",
            field=models.CharField(max_length=64, blank=True, default=""),
        ),
    ]
