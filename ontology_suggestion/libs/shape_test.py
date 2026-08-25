import json
import requests
from typing import TypedDict, Union, List
from django.conf import settings


class ShapeErrorObject(TypedDict):
    text: str
    about: str


class ValidationResult(TypedDict):
    error: List[ShapeErrorObject]
    info: List[str]
    shape_test_failed: bool


def test(ontology_purl: str) -> Union[ValidationResult, bool]:
    try:
        tesetUrl = "https://www.itb.ec.europa.eu/shacl/shacl/api/validate"
        headers = {"Content-Type": "application/json"}
        contentType = (
            "application/rdf+xml" if ".ttl" not in ontology_purl else "text/turtle"
        )
        ontologyContent = requests.get(ontology_purl)
        ontologyContent.raise_for_status()
        shapeTesterContent = requests.get(settings.ONTOLOGY_SHAPE_TEST_URL)
        shapeTesterContent.raise_for_status()
        data = {
            "contentToValidate": ontologyContent.text,
            "contentSyntax": contentType,
            "embeddingMethod": "STRING",
            "validationType": "extended",
            "reportSyntax": "application/ld+json",
            "externalRules": [
                {
                    "ruleSet": shapeTesterContent.text,
                    "embeddingMethod": "STRING",
                    "ruleSyntax": "text/turtle",
                }
            ],
            "addInputToReport": False,
            "addShapesToReport": False,
            "addRdfReportToReport": False,
            "rdfReportSyntax": "string",
            "wrapReportDataInCDATA": False,
        }
        response = requests.post(tesetUrl, json=data, headers=headers)
        if response.status_code != 200:
            try:
                res_content = response.json()
            except json.decoder.JSONDecodeError:
                res_content = {"message": "unknown error"}
            return ValidationResult(
                error=[ShapeErrorObject(text=res_content["message"], about="")],
                info=[],
                shape_test_failed=True,
            )

        response_data = response.json()
        response_data = response_data.get("@graph", None)
        if response_data is None:
            res_content = {"message": "unknown error"}
            return ValidationResult(
                error=[ShapeErrorObject(text=res_content["message"], about="")],
                info=[],
                shape_test_failed=True,
            )

        result = {"error": [], "info": [], "shape_test_failed": False}
        for report_item in response_data:
            level = report_item.get("sh:resultSeverity", {})
            if level.get("@id", "") == "sh:Warning":
                temp = {}
                temp["text"] = cleanErrorMessage(
                    report_item["sh:resultMessage"]["@value"]
                )
                temp["about"] = getErrorTargetFromMessage(temp["text"])
                result["error"].append(temp)
            elif level.get("@id", "") == "sh:Info":
                result["info"].append(report_item["sh:resultMessage"]["@value"])

        return result

    except:
        # raise
        res_content = {"message": "unknown error"}
        return ValidationResult(
            error=[ShapeErrorObject(text=res_content["message"], about="")],
            info=[],
            shape_test_failed=True,
        )


def getErrorTargetFromMessage(errorMesaage: str) -> str:
    target = errorMesaage.split("Recommended property:")[1]
    target = target.split("\n")[0]
    target = target.strip()
    return target


def cleanErrorMessage(errorMesaage: str) -> str:
    cleaned = errorMesaage.split("Need help?")[0]
    return cleaned
