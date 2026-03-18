from django.db import models
from user.models import UserModel
from django.contrib.postgres.indexes import GinIndex


class PubLinkModel(models.Model):
    creator = models.ForeignKey(UserModel, on_delete=models.DO_NOTHING)
    doi = models.CharField()
    citation = models.TextField()
    ontology_id = models.CharField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = "ontology_pub_links"
        indexes = [
            GinIndex(
                fields=["citation"], name="citation_index", opclasses=["gin_trgm_ops"]
            ),
        ]

    def to_dict(self):
        return {
            "creator": self.creator.id,
            "id": self.id,
            "doi": self.doi,
            "citation": self.citation,
            "ontology_id": self.ontology_id,
        }

    def __str__(self):
        return f"Ontology PubLink {self.ontology_id}:{self.doi}"
