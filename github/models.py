from django.db import models
from user.models import UserModel
from note.models import CLIENT_TS

ISSUE_TYPES = ["general", "termRequest"]


class GithubIssueRequestModel(models.Model):
    user = models.ForeignKey(UserModel, models.DO_NOTHING)
    created_at = models.DateTimeField()
    ontology_id = models.CharField()
    issue_content = models.CharField()
    issue_title = models.CharField()
    issue_url = models.CharField()
    client_ts = models.CharField()
    issue_type = models.CharField()

    class Meta:
        db_table = "github_issue_requests"

    def to_dict(self) -> dict:
        return {
            "ontology_id": self.ontology_id,
            "created_at": self.created_at,
            "issue_url": self.issue_url,
            "client_ts": self.client_ts,
            "issue_type": self.issue_type,
        }

    def __str__(self) -> str:
        return f"<GithubIssueRequest {self.issue_url}>"
