from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notification", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trigger", models.TextField()),
                ("recipient", models.EmailField(max_length=254)),
                ("success", models.BooleanField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "notification_logs",
                "ordering": ["-created_at"],
            },
        ),
    ]
