from django.db import models
from user.models import UserModel
from django.contrib.postgres.fields import ArrayField
from typing import Union


class CollectionModel(models.Model):
    title = models.CharField()
    description = models.CharField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)
    owner = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name='user_collections')
    ontology_ids = ArrayField(models.CharField)
    public = models.BooleanField(blank=True, null=True, default=True)

    class Meta:
        db_table = "collections"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "owner_id": self.owner.id,
            "ontology_ids": self.ontology_ids,
            "public": self.public,
        }

    def update(self, collection_id: Union[int, str]) -> Union[dict, bool]:
        # first check if the collection title is unique for the user
        record = CollectionModel.objects.filter(
            title=self.title, owner=self.owner
        ).first()
        if record and record.id != int(collection_id):
            return False

        record = CollectionModel.objects.filter(
            id=collection_id, owner=self.owner
        ).first()
        if record:
            record.title = self.title
            record.description = self.description
            record.updated_at = self.updated_at
            record.ontology_ids = self.ontology_ids
            record.save()
            return record.to_dict()

        return False

    def can_visit_edit(self, user_id: Union[int, str]) -> bool:
        return self.owner.id == user_id

    def __str__(self) -> str:
        return f"<Collection {self.title}>"
