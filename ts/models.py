from django.db import models


class TermDatasetLinkModel(models.Model):
    created_at = models.DateTimeField()
    curie = models.CharField()
    ontology_id = models.CharField()
    dataset_title = models.CharField()
    repo_name = models.CharField(null=True)

    class Meta:
        db_table = "term_dataset_links"

    def to_dict(self):
        return {
            "created_at": self.created_at,
            "curie": self.curie,
            "ontology_id": self.ontology_id,
            "dataset_title": self.dataset_title,
            "repo_name": self.repo_name,
        }

    def __str__(self):
        return f"<TermDatasetLinkModel {self.curie}>"
