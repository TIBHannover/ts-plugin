from django.db import models
from user.models import UserModel


PENDING = 0
REJECTED = 1
APPROVED = 2


class OntologySuggestionModel(models.Model):
    user = models.ForeignKey(UserModel, models.DO_NOTHING)
    created_at = models.DateTimeField()
    ontology_purl = models.CharField()
    reason = models.CharField()
    error_logs = models.CharField(blank=True, null=True)
    warning_logs = models.CharField(blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    collection_id = models.CharField(blank=True, null=True)
    extar_data = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "ontology_suggestions"

    def to_dict(self) -> dict:
        return {
            "ontology_purl": self.ontology_purl,
            "created_at": self.created_at,
            "status": self.status,
            "collection_id": self.collection_id,
            "user_id": self.user.id,
            "reason": self.reason,
            "error_logs": self.error_logs,
            "warning_logs": self.warning_logs,
            "extar_data": self.extar_data,
        }

    @staticmethod
    def get_by_purl(ontology_purl: str) -> dict:
        record = OntologySuggestionModel.objects.filter(
            ontology_purl=ontology_purl
        ).first()
        if record:
            return record.to_dict()
        return {}

    @staticmethod
    def get_by_user_id(user_id: int) -> list:
        user = UserModel.objects.get(id=user_id)
        if not user:
            return []
        records = OntologySuggestionModel.objects.filter(user=user).all()
        if records:
            return [record.to_dict() for record in records]
        return []

    @staticmethod
    def get_all() -> list:
        records = OntologySuggestionModel.objects.all()
        if records:
            return [record.to_dict() for record in records]
        return []

    @staticmethod
    def get_by_id(id: int) -> dict:
        record = OntologySuggestionModel.objects.get(id=id)
        if record:
            return record.to_dict()
        return {}

    def approve(self) -> bool:
        self.status = APPROVED
        self.save()
        return True

    def reject(self) -> bool:
        self.status = REJECTED
        self.save()
        return True

    def __str__(self) -> str:
        return f"<OntologySuggestion {self.ontology_purl}>"
