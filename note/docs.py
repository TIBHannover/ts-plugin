from rest_framework import serializers


class NoteCreateRequestSerializer(serializers.Serializer):
    title = serializers.CharField()
    content = serializers.CharField()
    ontology_id = serializers.CharField()
    semantic_component_type = serializers.ChoiceField(
        choices=["ontology", "class", "property", "individual"]
    )
    semantic_component_iri = serializers.CharField()
    semantic_component_label = serializers.CharField()
    visibility = serializers.ChoiceField(
        choices=["me", "internal", "public"], required=False, default="me"
    )
    parentOntology = serializers.CharField(required=False, allow_null=True)


class NoteUpdateRequestSerializer(serializers.Serializer):
    noteId = serializers.CharField()
    title = serializers.CharField(required=False)
    content = serializers.CharField(required=False)
    ontology_id = serializers.CharField(required=False)
    semantic_component_type = serializers.ChoiceField(
        choices=["ontology", "class", "property", "individual"], required=False
    )
    semantic_component_iri = serializers.CharField(required=False)
    semantic_component_label = serializers.CharField(required=False)
    visibility = serializers.ChoiceField(
        choices=["me", "internal", "public"], required=False, default="me"
    )
    parentOntology = serializers.CharField(required=False, allow_null=True)


class NoteListRequestSerializer(serializers.Serializer):
    ontology = serializers.CharField()
    artifact_iri = serializers.CharField(required=False)
    artifact_type = serializers.ChoiceField(
        choices=["ontology", "class", "property", "individual"], required=False
    )
    size = serializers.IntegerField(required=False, default=10)
    page = serializers.IntegerField(required=False, default=1)
    onlyOriginalNotes = serializers.BooleanField(required=False, default=False)


class NoteGetRequestSerializer(serializers.Serializer):
    withComments = serializers.BooleanField(required=False, default=False)
    ontology = serializers.CharField(required=False)


class NoteCreateCommentRequestSerializer(serializers.Serializer):
    noteId = serializers.CharField()
    content = serializers.CharField()


class NoteUpdateCommentRequestSerializer(serializers.Serializer):
    comment_id = serializers.CharField()
    content = serializers.CharField()


class ObjectDeleteRequestSerializer(serializers.Serializer):
    objectId = serializers.CharField()
    objectType = serializers.ChoiceField(choices=["note", "comment"])


class ObjectDeleteDataSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()


class NoteUpdateCommentDataSerializer(serializers.Serializer):
    comment_updated = serializers.DictField()


class NoteCreateCommentDataSerializer(serializers.Serializer):
    comment_created = serializers.DictField()


class NoteGetDataSerializer(serializers.Serializer):
    note = serializers.DictField()
    number_of_pinned = serializers.IntegerField()


class NoteListDataSerializer(serializers.Serializer):
    notes = serializers.ListField()
    stats = serializers.DictField()


class NoteCreateDataSerializer(serializers.Serializer):
    note_created = serializers.DictField()


class NoteUpdateDataSerializer(serializers.Serializer):
    note_updated = serializers.DictField()


class NoteCreateResponseSerializer(serializers.Serializer):
    _result = NoteCreateDataSerializer()


class NoteUpdateResponseSerializer(serializers.Serializer):
    _result = NoteCreateDataSerializer()


class NoteListResponseSerializer(serializers.Serializer):
    _result = NoteListDataSerializer()


class NoteGetResponseSerializer(serializers.Serializer):
    _result = NoteGetDataSerializer()


class NoteCreateCommentResponseSerializer(serializers.Serializer):
    _result = NoteCreateCommentDataSerializer()


class NoteUpdateCommentResponseSerializer(serializers.Serializer):
    _result = NoteUpdateCommentDataSerializer()


class ObjectDeleteResponseSerializer(serializers.Serializer):
    _result = ObjectDeleteDataSerializer()
