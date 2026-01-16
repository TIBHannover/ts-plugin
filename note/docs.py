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


class NoteCreateDataSerializer(serializers.Serializer):
    note_created = serializers.DictField()


class NoteCreateResponseSerializer(serializers.Serializer):
    _result = NoteCreateDataSerializer()
