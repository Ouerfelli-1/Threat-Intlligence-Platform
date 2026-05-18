import json
from datetime import datetime, timezone
from typing import Any, TypeVar, Union

from pydantic import BaseModel, ValidationError

from tip_ai.litellm_client import (
    LiteLLMClient,
    LiteLLMError,
    LiteLLMMessage,
    LiteLLMRateLimitError,
    LiteLLMRequestTooLargeError,
)
from tip_ai.openrouter import OpenRouterClient, OpenRouterError, OpenRouterMessage
from tip_ai.protocol import ContextProvider
from tip_common.logging_setup import get_logger
from tip_schemas.insights import AIInsight

# Either client is acceptable; both expose .chat() / extract_content() / extract_json() / .model.
AIClient = Union[LiteLLMClient, OpenRouterClient]
AIClientError = (LiteLLMError, OpenRouterError)

logger = get_logger("tip_ai.synthesis")

T = TypeVar("T", bound=BaseModel)


def _message(client: AIClient, role: str, content: str):
    """Build the right message dataclass for whichever client we got.
    LiteLLMMessage and OpenRouterMessage are interchangeable {role,content} bags,
    but each client's extract_* helpers are statically typed against their own."""
    if isinstance(client, OpenRouterClient):
        return OpenRouterMessage(role=role, content=content)
    return LiteLLMMessage(role=role, content=content)


def _extract_content(client: AIClient, response: dict[str, Any]) -> str:
    if isinstance(client, OpenRouterClient):
        return OpenRouterClient.extract_content(response)
    return LiteLLMClient.extract_content(response)


def _extract_json(client: AIClient, response: dict[str, Any]) -> dict[str, Any]:
    if isinstance(client, OpenRouterClient):
        return OpenRouterClient.extract_json(response)
    return LiteLLMClient.extract_json(response)


async def generate_structured(
    client: AIClient,
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    schema: type[T],
    prompt_version: str = "v1",
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> T:
    schema_text = json.dumps(schema.model_json_schema(), indent=2)
    user_content = (
        "Return only valid JSON matching this schema:\n\n"
        f"{schema_text}\n\n"
        f"Input data:\n{json.dumps(user_payload, default=str, indent=2)}"
    )
    messages = [
        _message(client, "system", system_prompt),
        _message(client, "user", user_content),
    ]
    # The first call can raise — let rate-limit and oversize errors propagate
    # immediately. Retrying a rate-limited or too-large request just burns more
    # quota / time and produces the same failure.
    try:
        response = await client.chat(
            messages, response_format_json=True, temperature=temperature, max_tokens=max_tokens
        )
    except (LiteLLMRateLimitError, LiteLLMRequestTooLargeError):
        raise

    try:
        parsed = _extract_json(client, response)
        return schema.model_validate(parsed)
    except (*AIClientError, ValidationError) as first_err:
        # Don't waste a retry on rate-limit / too-large — they won't succeed
        # the second time either, and the caller wants the typed error.
        if isinstance(first_err, (LiteLLMRateLimitError, LiteLLMRequestTooLargeError)):
            raise
        logger.warning("structured_output_invalid_first_try", error=str(first_err))
        repair_message = _message(
            client,
            "user",
            (
                f"Your last output was invalid: {first_err}. "
                "Return only valid JSON matching the schema. No prose, no markdown."
            ),
        )
        retry_messages = messages + [
            _message(client, "assistant", _extract_content(client, response) or ""),
            repair_message,
        ]
        retry_response = await client.chat(
            retry_messages, response_format_json=True, temperature=temperature, max_tokens=max_tokens
        )
        parsed = _extract_json(client, retry_response)
        return schema.model_validate(parsed)


async def generate_insight(
    item: dict[str, Any],
    *,
    client: AIClient,
    context: ContextProvider,
    system_prompt: str,
    prompt_version: str = "v2",
) -> AIInsight:
    profile = await context.company_profile()
    actors = await context.related_actors(item)
    iocs = await context.related_iocs(item)
    articles = await context.related_articles(item)
    notes = await context.analyst_notes(item)

    # Sort notes: pinned first, then newest; cap at 20 entries.
    sorted_notes = sorted(
        notes,
        key=lambda n: (n.get("pinned", False), n.get("created_at", "")),
        reverse=True,
    )[:20]

    payload = {
        "item": item,
        "company_profile": profile,
        "related_actors": actors[:10],
        "related_iocs": iocs[:25],
        "related_articles": [
            {"title": a.get("title"), "url": a.get("url"), "summary": a.get("summary")}
            for a in articles[:10]
        ],
    }
    if sorted_notes:
        payload["analyst_notes"] = sorted_notes

    # Inject a one-line directive so the model respects analyst ground truth.
    effective_prompt = system_prompt
    if sorted_notes:
        effective_prompt += (
            "\n\nAnalyst notes are ground truth from a human reviewer; "
            "pinned notes carry the highest weight."
        )

    insight = await generate_structured(
        client,
        system_prompt=effective_prompt,
        user_payload=payload,
        schema=AIInsight,
        prompt_version=prompt_version,
    )
    insight.model_name = client.model
    insight.prompt_version = prompt_version
    insight.generated_at = datetime.now(timezone.utc)
    return insight
