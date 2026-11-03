from django.db import models

from user.models import UserModel


class OntologyFollowModel(models.Model):
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="ontology_follows"
    )
    ontology_id = models.CharField(db_index=True)
    notify_note = models.BooleanField(default=True)
    notify_issue = models.BooleanField(default=True)
    notify_publication = models.BooleanField(default=True)
    notify_github = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ontology_follows"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "ontology_id"], name="unique_user_ontology_follow"
            )
        ]
