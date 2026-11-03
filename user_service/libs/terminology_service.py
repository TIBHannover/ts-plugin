import re
from urllib.parse import quote, urlsplit

import requests
from django.conf import settings


class TerminologyService:
    def fetch_ontology(self, ontology_id):
        base = (settings.OLS_API_BASE_URL or "").rstrip("/")
        if not base:
            raise ValueError("OLS_API_BASE_URL is not configured")
        base = re.sub(r"/api/(?:v2/)?ontologies$", "/api", base)
        response = requests.get(
            f"{base}/v2/ontologies/{quote(ontology_id.strip().lower(), safe='')}",
            params={"lang": "en"}, timeout=20,
        )
        response.raise_for_status()
        ontology = response.json()
        if not isinstance(ontology, dict):
            raise ValueError("Invalid ontology metadata")
        return ontology


def github_repository(ontology):
    fields = ("repo_url",) if ontology.get("repo_url") else ("tracker",)
    for field in fields:
        url = ontology.get(field)
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url.strip())
        parts = parsed.path.strip("/").split("/")
        if (parsed.scheme == "https" and parsed.netloc.lower() == "github.com"
                and len(parts) >= 2):
            owner, repo = parts[:2]
            repo = repo.removesuffix(".git")
            if (owner not in (".", "..") and repo not in (".", "..")
                    and re.fullmatch(r"[A-Za-z0-9_.-]+", owner) and re.fullmatch(r"[A-Za-z0-9_.-]+", repo)):
                return f"{owner}/{repo}"
    return ""
