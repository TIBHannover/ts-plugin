from django.contrib import admin


class OntologyIdListFilter(admin.SimpleListFilter):
    title = "ontology id"
    parameter_name = "ontology_id"

    def lookups(self, request, model_admin):
        ontology_ids = (
            model_admin.get_queryset(request)
            .values_list("ontology_ids", flat=True)
            .distinct()
        )
        return [
            (value, value)
            for value in sorted({value for values in ontology_ids for value in values or []})
        ]

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(ontology_ids__contains=[self.value()])
        return queryset
