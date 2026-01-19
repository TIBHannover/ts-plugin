from rest_framework import serializers


class TermSetCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False)
    visibility = serializers.ChoiceField(
        choices=["me", "internal", "public"], required=False, default="me"
    )
    terms = serializers.ListField(required=False, default=[])


class TermSetUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False)
    visibility = serializers.ChoiceField(
        choices=["me", "internal", "public"], required=False, default="me"
    )
    terms = serializers.ListField(required=False)


class TermSetGetRequestSerializer(serializers.Serializer):
    pass


class AddTermRequestSerializer(serializers.Serializer):
    term = serializers.DictField()


class RemoveTermRequestSerializer(serializers.Serializer):
    termId = serializers.CharField()


class TermSetCreateDataSerializer(serializers.Serializer):
    term_set = serializers.DictField()


class TermSetUpdateDataSerializer(serializers.Serializer):
    term_set = serializers.DictField()


class TermSetGetDataSerializer(serializers.Serializer):
    term_set = serializers.DictField()


class TermSetDeleteDataSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()


class TermSetAddTermDataSerializer(serializers.Serializer):
    added = serializers.BooleanField()


class TermSetRemoveTermDataSerializer(serializers.Serializer):
    removed = serializers.BooleanField()


class TermSetCreateResponseSerializer(serializers.Serializer):
    _result = TermSetCreateDataSerializer()


class TermSetUpdateResponseSerializer(serializers.Serializer):
    _result = TermSetUpdateDataSerializer()


class TermSetGetResponseSerializer(serializers.Serializer):
    _result = TermSetGetDataSerializer()


class TermSetDeleteResponseSerializer(serializers.Serializer):
    _result = TermSetDeleteDataSerializer()


class TermSetAddTermResponseSerializer(serializers.Serializer):
    _result = TermSetAddTermDataSerializer()


class TermSetRemoveTermResponseSerializer(serializers.Serializer):
    _result = TermSetRemoveTermDataSerializer()
