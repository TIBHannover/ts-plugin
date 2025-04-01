from django.db import models
import uuid
from user.models import UserModel


VISIBILITIES_VALUES = ["me", "internal", "public"]


class TermSetModel(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, unique=True, editable=False
    )
    name = models.CharField(blank=False, null=False)
    description = models.CharField()
    creator = models.ForeignKey(
        UserModel, models.DO_NOTHING, related_name="user_term_sets"
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)
    visibility = models.CharField(default="me")

    class Meta:
        db_table = "term_sets"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "creator": self.creator.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "visibility": self.visibility,
            "terms": [term.to_dict() for term in self.terms.all()],
        }

    def save(self, **kwargs):
        if self.visibility not in VISIBILITIES_VALUES:
            self.visibility = "me"
        super().save(**kwargs)

    def __str__(self) -> str:
        return f"<Term_set {self.id}>"


class TermsModel(models.Model):
    iri = models.CharField(null=False)
    term_type = models.CharField()
    term_set = models.ForeignKey(TermSetModel, models.CASCADE, related_name="terms")
    metadata = models.JSONField(null=False)

    class Meta:
        db_table = "terms"

    def to_dict(self) -> dict:
        return {"iri": self.iri, "type": self.term_type, "json": self.metadata}
