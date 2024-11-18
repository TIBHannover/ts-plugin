# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AlembicVersion(models.Model):
    version_num = models.CharField(primary_key=True, max_length=32)

    class Meta:
        managed = False
        db_table = "alembic_version"


class Collections(models.Model):
    title = models.CharField()
    description = models.CharField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)
    owner = models.ForeignKey("Users", models.DO_NOTHING)
    ontology_ids = models.TextField()  # This field type is a guess.
    public = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "collections"


class GithubIssueRequests(models.Model):
    user = models.ForeignKey("Users", models.DO_NOTHING)
    created_at = models.DateTimeField()
    ontology_id = models.CharField()
    issue_content = models.CharField()
    issue_title = models.CharField()
    issue_url = models.CharField()
    client_ts = models.CharField()
    issue_type = models.CharField()

    class Meta:
        managed = False
        db_table = "github_issue_requests"


class NoteComments(models.Model):
    creator = models.ForeignKey("Users", models.DO_NOTHING)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)
    content = models.CharField()
    note = models.ForeignKey("Notes", models.DO_NOTHING)
    active = models.BooleanField()

    class Meta:
        managed = False
        db_table = "note_comments"


class Notes(models.Model):
    creator = models.ForeignKey("Users", models.DO_NOTHING)
    created_at = models.DateTimeField()
    ontology_id = models.CharField()
    content = models.CharField()
    title = models.CharField()
    client_ts = models.CharField()
    semantic_component_type = models.CharField()
    semantic_component_iri = models.CharField()
    visibility = models.CharField()
    active = models.BooleanField()
    updated_at = models.DateTimeField(blank=True, null=True)
    pinned = models.BooleanField(blank=True, null=True)
    parent_ontology_id = models.CharField(blank=True, null=True)
    semantic_component_label = models.CharField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "notes"


class OntologySuggestions(models.Model):
    user = models.ForeignKey("Users", models.DO_NOTHING)
    created_at = models.DateTimeField()
    ontology_purl = models.CharField()
    reason = models.CharField()
    error_logs = models.CharField(blank=True, null=True)
    warning_logs = models.CharField(blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    collection_id = models.CharField(blank=True, null=True)
    extar_data = models.JSONField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "ontology_suggestions"


class Reports(models.Model):
    created_at = models.DateTimeField()
    reported_object_type = models.CharField()
    reported_object_id = models.IntegerField()
    reporter = models.ForeignKey("Users", models.DO_NOTHING)
    report_content = models.CharField(blank=True, null=True)
    status = models.CharField(blank=True, null=True)
    client_ts = models.CharField()

    class Meta:
        managed = False
        db_table = "reports"


class Roles(models.Model):
    user = models.ForeignKey("Users", models.DO_NOTHING)
    created_at = models.DateTimeField()
    target_object_id = models.CharField()
    target_object_type = models.CharField()
    role = models.CharField()
    client_ts = models.CharField()
    role_holder_email = models.CharField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "roles"


class SearchSettings(models.Model):
    title = models.CharField()
    user = models.ForeignKey("Users", models.DO_NOTHING)
    description = models.CharField(blank=True, null=True)
    setting = models.JSONField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "search_settings"
