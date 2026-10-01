import logging
import os
import time
from typing import Any

import requests
from openai import OpenAI

logger = logging.getLogger(__name__)

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["LLM_API_KEY"])
model = os.environ["LLM_MODEL"]
generation_url = "https://openrouter.ai/api/v1/generation"


def call_openrouter(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    require_tool: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
        extra_body={"usage": {"include": True}},
        **({"tools": tools} if tools else {}),
        **({"tool_choice": "required"} if tools and require_tool else {}),
    )
    usage = _as_dict(response.usage) if response.usage else {}
    upstream_cost = (usage.get("cost_details") or {}).get("upstream_inference_cost")
    if usage.get("cost") == 0 and upstream_cost:
        usage["cost"] = upstream_cost
    if usage.get("cost") is None or (
        usage.get("cost") == 0 and usage.get("total_tokens", 0) > 0
    ):
        cost = get_generation_cost(response.id)
        if cost is not None:
            usage["cost"] = cost
    return _as_dict(response.choices[0].message), usage


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    return dict(value)


def get_generation_cost(generation_id):
    try:
        for delay in (0, 0.5, 1):
            if delay:
                time.sleep(delay)
            response = requests.get(
                generation_url,
                params={"id": generation_id},
                headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                timeout=(3.05, 10),
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            cost = data.get("total_cost") or data.get("usage")
            if cost:
                return cost
    except Exception:
        logger.exception("Unable to retrieve OpenRouter cost for %s", generation_id)
    return None
