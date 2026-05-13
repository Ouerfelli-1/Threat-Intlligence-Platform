import json
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from tip_ai.openrouter import OpenRouterClient, OpenRouterError, OpenRouterMessage
from tip_ai.protocol import ContextProvider
from tip_common.logging_setup import get_logger
from tip_schemas.insights import AIInsight

logger = get_logger("tip_ai.synthesis")

T = TypeVar("T", bound=BaseModel)


async def generate_structured(
    client: OpenRouterClient,
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    schema: type[T],
    prompt_version: str = "v1",
    temperature: float = 0.2,
) -> T:
    schema_text = json.dumps(schema.model_json_schema(), indent=2)
    user_content = (
        "Return only valid JSON matching this schema:\n\n"
        f"{schema_text}\n\n"
        f"Input data:\n{json.dumps(user_payload, default=str, indent=2)}"
    )
    messages = [
        OpenRouterMessage(role="system", content=system_prompt),
        OpenRouterMessage(role="user", content=user_content),
    ]
    response = await client.chat(messages, response_format_json=True, temperature=temperature)

    try:
        parsed = OpenRouterClient.extract_json(response)
        return schema.model_validate(parsed)
    except (OpenRouterError, ValidationError) as first_err:
        logger.warning("structured_output_invalid_first_try", error=str(first_err))
        repair_message = OpenRouterMessage(
            role="user",
            content=(
                f"Your last output was invalid: {first_err}. "
                "Return only valid JSON matching the schema. No prose, no markdown."
            ),
        )
        retry_messages = messages + [
            OpenRouterMessage(
                role="assistant",
                content=OpenRouterClient.extract_content(response) or "",
            ),
            repair_message,
        ]
        retry_response = await client.chat(
            retry_messages, response_format_json=True, temperature=temperature
        )
        parsed = OpenRouterClient.extract_json(retry_response)
        return schema.model_validate(parsed)


async def generate_insight(
    item: dict[str, Any],
    *,
    client: OpenRouterClient,
    context: ContextProvider,
    system_prompt: str,
    prompt_version: str = "v1",
) -> AIInsight:
    profile = await context.company_profile()
    actors = await context.related_actors(item)
    iocs = await context.related_iocs(item)
    articles = await context.related_articles(item)

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
    insight = await generate_structured(
        client,
        system_prompt=system_prompt,
        user_payload=payload,
        schema=AIInsight,
        prompt_version=prompt_version,
    )
    insight.model_name = client.model
    insight.prompt_version = prompt_version
    insight.generated_at = datetime.now(timezone.utc)
    return insight
