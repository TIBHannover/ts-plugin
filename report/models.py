from django.db import models
from user.models import UserModel


PENDING_STATUS = "pending"
RESOLVED_STATUS = "resolved"


class ReportModel(models.Model):
    created_at = models.DateTimeField()
    reported_object_type = models.CharField()
    reported_object_id = models.IntegerField()
    reporter = models.ForeignKey(UserModel, on_delete=models.DO_NOTHING)
    report_content = models.CharField(blank=True, null=True)
    status = models.CharField(blank=True, null=True, default=PENDING_STATUS)
    client_ts = models.CharField()

    class Meta:
        db_table = "reports"

    def to_dict(self):
        return {
            "created_at": self.created_at,
            "reported_object_type": self.reported_object_type,
            "client_ts": self.client_ts
        }

    def resolve(self) -> bool:
        self.status = RESOLVED_STATUS
        self.save()
        return True

    @staticmethod
    def get_all_pending_reports() -> list:
        reports = ReportModel.objects.filter(status=PENDING_STATUS).all()
        return reports

    @staticmethod
    def get_pending_reports_for_client(client_id: str) -> list:
        reports = ReportModel.objects.filter(
            status=PENDING_STATUS, client_ts=client_id
        ).all()
        return reports
