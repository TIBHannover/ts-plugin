from django.db import models


class TermDatasetLinkModel(models.Model):
    created_at = models.DateTimeField()
    curie = models.CharField()
    term_label = models.CharField(null=True)
    ontology_id = models.CharField()
    dataset_title = models.CharField()
    dataset_description = models.TextField(null=True)
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
            "dataset_description": self.dataset_description,
            "term_label": self.term_label,
        }

    def __str__(self):
        return f"<TermDatasetLinkModel {self.curie}>"


class HarvestFailureModel(models.Model):
    created_at = models.DateTimeField()
    dataset_title = models.CharField()
    error_code = models.IntegerField()

    class Meta:
        db_table = "harvest_failures"

    def to_dict(self):
        return {
            "created_at": self.created_at,
            "dataset_title": self.dataset_title,
            "error_code": self.error_code,
        }

    def __str__(self):
        return f"<HarvestFailureModel {self.dataset_title}>"
