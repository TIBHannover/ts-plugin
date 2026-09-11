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
            "definition": self.definition[:300],
            "subjects": self.subjects,
            "collection": self.collection,
            "importsFrom": self.importsFrom,
            "exportsTo": self.exportsTo,
            "label": self.label,
            "lang": self.lang,
        }

    def __str__(self):
        return self.label


class AiAssistSession(models.Model):
    run_id = models.UUIDField(primary_key=True, editable=False)
    user = models.ForeignKey(
        "user.UserModel",
        on_delete=models.SET_NULL,
        related_name="ai_assist_sessions",
        null=True,
    )
    workflow = models.CharField(max_length=32)
    context_size = models.PositiveBigIntegerField(default=0)
    prompt_tokens = models.PositiveBigIntegerField(default=0)
    completion_tokens = models.PositiveBigIntegerField(default=0)
    total_tokens = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_assist_sessions"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("-created_at",), name="ai_asst_created_idx")]

    def __str__(self):
        return str(self.run_id)


class AiAssistUserInput(models.Model):
    session = models.ForeignKey(
        AiAssistSession, on_delete=models.CASCADE, related_name="user_inputs"
    )
    sequence = models.PositiveIntegerField()
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_assist_user_inputs"
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("session", "sequence"), name="unique_ai_assist_user_input_order"
            )
        ]


class AiAssistModelOutput(models.Model):
    session = models.ForeignKey(
        AiAssistSession, on_delete=models.CASCADE, related_name="model_outputs"
    )
    sequence = models.PositiveIntegerField()
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_assist_model_outputs"
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("session", "sequence"), name="unique_ai_assist_model_output_order"
            )
        ]
