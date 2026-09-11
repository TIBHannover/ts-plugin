
def convert_to_str(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ". ".join(str(item) for item in value)
    return ""

def get_parent_from_term(term_v2):
    linkedEntities = term_v2.get("linkedEntities", {})
    directParentIri = term_v2.get("directParent", "")
    directParentLabel = linkedEntities.get(directParentIri,{}).get("label", [])
    return {"label": directParentLabel, "iri": directParentIri}

def get_term_type(term_v2):
    types = term_v2.get("type", ["Error: Unknown types for this term"])
    if types[0] != "class" and types[0] != "property" and types[0] != "individual":
        return "Error: Unknown term type"
    return types[0]
