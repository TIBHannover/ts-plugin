from django.db import models


class OntologyGitHubCache(models.Model):
    ontology_id = models.CharField(unique=True)
    metadata = models.JSONField(default=dict)
    metadata_expires_at = models.DateTimeField(null=True)
    updates = models.JSONField(default=dict)
    updates_expires_at = models.DateTimeField(null=True)
    window_end = models.DateTimeField(null=True)
