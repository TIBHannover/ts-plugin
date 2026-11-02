from django.db import models

from user.models import UserModel


class OntologyFollowModel(models.Model):
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="ontology_follows"
    )
    ontology_id = models.CharField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ontology_follows"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "ontology_id"], name="unique_user_ontology_follow"
            )
        ]
