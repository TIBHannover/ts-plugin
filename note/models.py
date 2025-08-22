from django.db import models
from user.models import UserModel
from typing import Union
from report.models import ReportModel
from user.libs.auth import Auth

CLIENT_TS = ["general", "nfdi4chem", "nfdi4ing"]
VISIBILITIES_VALUES = ["me", "internal", "public"]
SC_TYPES = ["ontology", "class", "property", "individual"]
_Q = models.Q


class NoteModel(models.Model):
    creator = models.ForeignKey(UserModel, models.DO_NOTHING)
    created_at = models.DateTimeField()
    ontology_id = models.CharField()
    content = models.CharField()
    title = models.CharField()
    client_ts = models.CharField()
    semantic_component_type = models.CharField()
    semantic_component_iri = models.CharField()
    visibility = models.CharField(default="me")
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    pinned = models.BooleanField(blank=True, null=True, default=False)
    parent_ontology_id = models.CharField(blank=True, null=True)
    semantic_component_label = models.CharField(blank=True, null=True)

    class Meta:
        db_table = "notes"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ontology_id": self.ontology_id,
            "created_at": self.created_at,
            "client_ts": self.client_ts,
            "semantic_component_type": self.semantic_component_type,
            "semantic_component_iri": self.semantic_component_iri,
            "semantic_component_label": self.semantic_component_label,
            "title": self.title,
            "content": self.content,
            "visibility": self.visibility,
            "created_by": UserModel.get_user_name_by_id(self.creator.id),
            "pinned": self.pinned,
            "parent_ontology": self.parent_ontology_id,
        }

    def save(self, **kwargs):
        client_ts_is_valid = self.client_ts in CLIENT_TS
        visibility_is_valid = self.visibility in VISIBILITIES_VALUES
        type_is_valid = self.semantic_component_type in SC_TYPES
        if not visibility_is_valid:
            self.visibility = "me"
        if client_ts_is_valid and type_is_valid:
            super().save(**kwargs)
        else:
            return

    def delete(self, **kwargs):
        self.active = False
        self.save()

    def update_record(self, updates: dict) -> Union[bool, object]:
        if not self:
            return False
        for column, new_value in updates.items():
            setattr(self, column, new_value)

        self.save()
        return self

    @staticmethod
    def get_notes_by_conditions(conditions: dict) -> dict:
        base_condition_set = _Q(active=True) & _Q(client_ts=conditions["client_ts"])
        ontology_condition_set = _Q(ontology_id=conditions["ontology_id"]) & _Q(pinned=conditions["pinned"])
        parent_ontology_condition_set = _Q(parent_ontology_id=conditions["ontology_id"])
        visibility_condition_set = _Q(visibility__in=conditions["visibilities"]) | _Q(creator_id=conditions["user_id"])

        if conditions.get("semantic_component_type"):
            base_condition_set &= _Q(semantic_component_type=conditions["semantic_component_type"])

        if conditions.get("semantic_component_iri"):
            base_condition_set &= _Q(semantic_component_iri=conditions["semantic_component_iri"])
            ontology_condition_set = _Q(ontology_id=conditions["ontology_id"])

        if conditions.get("get_notes_from_children"):
            ontology_condition_set = _Q(parent_ontology_condition_set) | ontology_condition_set

        count_of_all_notes = NoteModel.objects.filter(
            _Q(base_condition_set & visibility_condition_set & ontology_condition_set)
        ).count()
        if count_of_all_notes == 0:
            return {"notes": [], "count_of_all_notes": 0}

        start = conditions.get("offset", 0)
        end = conditions.get("limit", 10) + start
        notes = NoteModel.objects.filter(
            _Q(base_condition_set & visibility_condition_set & ontology_condition_set)
        ).order_by("created_at")[start: end]

        if not notes:
            return {"notes": [], "count_of_all_notes": count_of_all_notes}
        result = []
        auth = Auth()
        for note in notes:
            comment_count = note.note_comments.filter(active=True).count()
            note_dict = note.to_dict()
            note_dict["imported"] = False if conditions["ontology_id"] == note_dict["ontology_id"] else True
            note_dict["comments_count"] = comment_count
            note_report = ReportModel.objects.filter(reported_object_type="note",
                                                     reported_object_id=note_dict["id"]).first()
            note_dict["can_edit"] = auth.user_can_edit_object(
                objectModel=NoteModel,
                object_id=note_dict["id"],
                role_target_object_id=note_dict["ontology_id"],
            )
            note_dict["is_reported"] = True if note_report else False

            result.append(note_dict)

        return {"notes": result, "count_of_all_notes": count_of_all_notes}

    @staticmethod
    def user_can_edit(note_id: Union[int, str], user_id: Union[int, str]) -> bool:
        note = NoteModel.objects.filter(id=note_id).first()
        if not note:
            return False
        if not note.active:
            return False
        if note.creator.id != user_id:
            return False
        return True

    def can_visit(self, user_id: Union[int, str], client_ts: str, is_guest: bool):
        visibilities = ['public'] if is_guest else ['public', 'internal']
        if self.client_ts != client_ts:
            return False

        if self.visibility not in visibilities and self.creator.id != user_id:
            return False

        return True

    @staticmethod
    def get_visibility(note_id: Union[int, str]) -> bool:
        note = NoteModel.objects.filter(id=note_id, active=True).first()
        if note:
            return note.visibility
        return False

    def __str__(self) -> str:
        return f"<NoteModel {self.title}>"


class NoteCommentModel(models.Model):
    creator = models.ForeignKey(UserModel, models.DO_NOTHING, related_name="user_comments")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)
    content = models.CharField()
    note = models.ForeignKey(NoteModel, models.DO_NOTHING, related_name="note_comments")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "note_comments"

    def delete(self, **kwargs):
        self.active = False
        self.save()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content": self.content,
            "note_id": self.note.id,
            "created_by": self.creator.name,
        }

    def update_record(self, updates: dict) -> Union[bool, object, None]:
        for column, new_value in updates.items():
            setattr(self, column, new_value)

        self.save()
        return self

    @staticmethod
    def user_can_edit(comment_id: Union[int, str], user_id: Union[int, str]) -> bool:
        comment = NoteCommentModel.objects.filter(id=comment_id).first()
        if not comment:
            return False
        if not comment.active:
            return False
        if comment.creator_id != user_id:
            return False

        return True

    @staticmethod
    def get_visibility(comment_id: Union[int, str]) -> bool:
        comment = NoteCommentModel.objects.filter(id=comment_id, active=True).first()
        if comment:
            return comment.note.visibility
        return False

    def __str__(self) -> str:
        return f"<NoteCommentModel {self.id}>"
