from django.db import models
from django.utils import timezone


class Ontology(models.Model):
    ontologyId = models.CharField(max_length=255, primary_key=True)
    repo_url = models.CharField(max_length=2048)
    definition = models.TextField()
    subjects = models.JSONField(default=list)
    collection = models.JSONField(default=list)
    importsFrom = models.JSONField(default=list)
    exportsTo = models.JSONField(default=list)
    label = models.CharField(max_length=255)
    lang = models.JSONField(default=list)
    loaded = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "ontologies"

    def to_dict(self):
        return {
            "ontologyId": self.ontologyId,
            "repo_url": self.repo_url,
            "definition": self.definition,
            "subjects": self.subjects,
            "collection": self.collection,
            "importsFrom": self.importsFrom,
            "exportsTo": self.exportsTo,
            "label": self.label,
            "lang": self.lang,
            "loaded": self.loaded,
        }

    def __str__(self):
        return self.label
