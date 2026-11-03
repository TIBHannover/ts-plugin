from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ontology_follow", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ontologyfollowmodel",
            name="notify_note",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="ontologyfollowmodel",
            name="notify_issue",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="ontologyfollowmodel",
            name="notify_publication",
            field=models.BooleanField(default=True),
        ),
    ]
