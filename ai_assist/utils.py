
def convert_to_str(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ". ".join(str(item) for item in value)
    return ""

def get_parent_from_term(term_v2):
    linkedEntities = term_v2.get("linkedEntities", {})
    directParentIri = term_v2.get("directParent", "")
    if isinstance(directParentIri, list):
        directParentIri = next(
            (iri for iri in directParentIri if isinstance(iri, str)), ""
        )
    if not isinstance(directParentIri, str):
        directParentIri = ""
    if not isinstance(linkedEntities, dict):
        linkedEntities = {}
    directParentLabel = linkedEntities.get(directParentIri,{}).get("label", [])
    return {"label": directParentLabel, "iri": directParentIri}

def get_term_type(term_v2):
    types = term_v2.get("type", ["Error: Unknown types for this term"])
    if isinstance(types, str):
        types = [types]
    if not isinstance(types, list):
        return "Error: Unknown term type"
    return next(
        (term_type for term_type in types if term_type in ("class", "property", "individual")),
        "Error: Unknown term type",
    )
