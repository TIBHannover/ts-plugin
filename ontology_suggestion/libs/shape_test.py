import requests
from typing import TypedDict, Union, List
from django.conf import settings


class ShapeErrorObject(TypedDict):
    text: str
    about: str


class ValidationResult(TypedDict):
    error: List[ShapeErrorObject]
    info: List[str]


def testShape(ontology_purl: str) -> Union[ValidationResult, bool]:
    try:
        tesetUrl = "https://www.itb.ec.europa.eu/shacl/shacl/api/validate"
        headers = {"Content-Type": "application/json", "Accept": "text/turtle"}
        contentType = (
            "application/rdf+xml" if ".ttl" not in ontology_purl else "text/turtle"
        )
        data = {
            "contentToValidate": ontology_purl,
            "contentSyntax": contentType,
            "embeddingMethod": "URL",
            "validationType": "extended",
            "reportSyntax": "application/ld+json",
            "externalRules": [
                {
                    "ruleSet": settings.ONTOLOGY_SHAPE_TEST_URL,
                    "embeddingMethod": "URL",
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
            return False

        response_data = response.json()
        response_data = response_data.get("@graph", None)
        if response_data is None:
            return False

        result = {"error": [], "info": []}
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
        return False


def getErrorTargetFromMessage(errorMesaage: str) -> str:
    target = errorMesaage.split("Recommended property:")[1]
    target = target.split("\n")[0]
    target = target.strip()
    return target


def cleanErrorMessage(errorMesaage: str) -> str:
    cleaned = errorMesaage.split("Need help?")[0]
    return cleaned
