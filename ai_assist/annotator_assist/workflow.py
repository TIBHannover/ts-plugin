import json
import itertools
import logging
import re
import time
from openai import APIConnectionError, APITimeoutError

from ai_assist.functions import allowed_ontology_ids

logger = logging.getLogger(__name__)
FIELD_RE = re.compile(r"(?<!\w)([A-Z](?:[a-z0-9]*|[A-Z0-9]*)(?: (?:[A-Z](?:[a-z0-9]*|[A-Z0-9]*)|of|and)){0,4}):")
NUMERIC_RE = re.compile(r"[\d.,+\-\s]+\Z")
JSON_LD_CONTEXT = {
    "oa": "http://www.w3.org/ns/oa#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "schema": "https://schema.org/",
    "source": {"@id": "rdf:value", "@type": "@json"},
    "body": {"@id": "oa:hasBody", "@type": "@id"},
    "target": "oa:hasTarget",
    "hasSource": {"@id": "oa:hasSource", "@type": "@id"},
    "location": {"@id": "rdf:value", "@type": "@json"},
    "annotation_mode": "http://www.w3.org/2000/01/rdf-schema#comment",
    "ontologyId": "schema:identifier",
    "termLabel": "schema:name",
    "termType": "schema:additionalType",
}


def collection_ontologies():
    ontology_ids = allowed_ontology_ids()
    if not ontology_ids:
        raise RuntimeError("NFDI4CHEM ontology collection is unavailable.")
    return ontology_ids


def _field_from_match(text, matches, index):
    match = matches[index]
    end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
    raw = text[match.end():end]
    return {
        "label": match.group(1), "value": raw.strip(),
        "label_start": match.start(1), "label_end": match.end(1),
        "value_start": match.end() + len(raw) - len(raw.lstrip()),
        "value_end": end - len(raw) + len(raw.rstrip()),
    }


def extract_metadata(text, run_id=None, deadline=None):
    matches = list(itertools.islice(FIELD_RE.finditer(text), 2001))
    complete = len(matches) <= 2000
    fields = [_field_from_match(text, matches, index) for index in range(min(len(matches), 2000))]
    if matches:
        sample = re.search(r"sample\s*-\s*(.+)$", text[:matches[0].start()], re.IGNORECASE)
        if sample:
            fields.insert(0, {"label": "Sample", "value": sample.group(1).strip(), "label_start": sample.start(), "label_end": sample.start() + len("sample"), "value_start": sample.start(1), "value_end": sample.end(1)})

    from ai_assist.model_client import call_openrouter
    from ai_assist.session_logging import record_model_output

    for offset in range(0, len(text), 5000):
        if deadline is not None and deadline - time.monotonic() < 2:
            complete = False
            break
        chunk = text[offset:offset + 5000]
        try:
            message, usage = call_openrouter([
                {"role": "system", "content": "Extract experiment metadata from the text. Return only JSON: {\"fields\":[{\"label\":\"\",\"value\":\"\",\"quote\":\"\"}]}. Each quote must be copied exactly from the input. Do not invent values or ontology terms."},
                {"role": "user", "content": chunk},
            ], [], timeout_seconds=min(15, deadline - time.monotonic()) if deadline is not None else 15)
        except (APIConnectionError, APITimeoutError):
            logger.warning("Model provider unavailable for metadata extraction in run %s", run_id)
            complete = False
            break
        if run_id:
            record_model_output(run_id, message, usage)
        try:
            extracted = json.loads(message.get("content") or "").get("fields", [])
        except (AttributeError, TypeError, json.JSONDecodeError):
            continue
        for field in extracted if isinstance(extracted, list) else []:
            if not isinstance(field, dict):
                continue
            label, value, quote = (field.get(name) for name in ("label", "value", "quote"))
            if all(isinstance(item, str) and item.strip() for item in (label, value, quote)) and value in quote and quote in chunk:
                start = text.find(quote, offset, offset + len(chunk))
                value_start = text.find(value, start, start + len(quote))
                fields.append({"label": label, "value": value, "label_start": start, "label_end": start + len(quote), "value_start": value_start, "value_end": value_start + len(value)})
    return list({(field["label"], field["value"], field["value_start"]): field for field in fields if field["value"]}.values()), complete


def _value_target(field):
    value = field["value"]
    if len(value) > 80 or "_" in value or "(" in value or NUMERIC_RE.fullmatch(value):
        return None
    return "value", value, field["label"]


def annotate_text(text, run_id=None):
    from ai_assist.search_agent.agent import run_batch_search_turn

    deadline = time.monotonic() + 55
    fields, complete = extract_metadata(text, run_id, deadline)
    examples = {}
    for field in fields:
        examples.setdefault(field["label"], [])
        if field["value"] not in examples[field["label"]] and len(examples[field["label"]]) < 3:
            examples[field["label"]].append(field["value"])
    targets = list(dict.fromkeys(
        target
        for field in fields
        for target in (("key", field["label"], json.dumps(examples[field["label"]])), _value_target(field))
        if target is not None
    ))

    ontology_ids = collection_ontologies()
    matches = {}
    modes = set()
    search_complete = True
    for offset in range(0, len(targets), 5):
        if deadline - time.monotonic() < 2:
            search_complete = False
            break
        group = targets[offset:offset + 5]
        for _ in range(2):
            try:
                found, valid, mode, search_exhausted = run_batch_search_turn(group, run_id, min(15, deadline - time.monotonic()), ontology_ids)
            except TimeoutError:
                search_complete = False
                break
            if valid:
                matches.update(found)
                modes.add(mode)
                search_complete &= search_exhausted
                break
        else:
            raise RuntimeError("Terminology search returned an invalid result.")
    mode = ", ".join(sorted(modes)) or "no matches"
    graph = [{"@id": "_:dataset", "source": text, "annotation_mode": f"{'Complete' if complete and search_complete else 'Partial'} terminology annotation ({mode})."}]
    output_limited = False
    for field in fields:
        key_target = "key", field["label"], json.dumps(examples[field["label"]])
        for kind, target in (("field", key_target), ("value", _value_target(field))):
            term = matches.get(target) if target else None
            if term and len(graph) <= 2000:
                graph.append({
                    "@type": "oa:Annotation",
                    "body": term["iri"],
                    "ontologyId": term["ontologyId"],
                    "termLabel": term["label"],
                    "termType": term.get("type", "class"),
                    "target": {"hasSource": "_:dataset", "location": {"label": field["label"], "value": field["value"], "start": field["label_start"] if kind == "field" else field["value_start"], "end": field["label_end"] if kind == "field" else field["value_end"], "kind": kind}},
                })
            elif term:
                output_limited = True
                graph[0]["annotation_mode"] = f"Partial terminology annotation ({mode}); output limit reached."
    return {"@context": JSON_LD_CONTEXT, "@graph": graph}, complete and search_complete and not output_limited
