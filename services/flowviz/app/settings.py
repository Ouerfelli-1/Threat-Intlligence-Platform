from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "flowviz"
    service_port: int = 8008
    database_schema: str = "flowviz"

    # Flowviz needs the smartest available model — attack-flow generation
    # requires multi-step spatial reasoning + adherence to a complex JSON
    # schema (10+ node types, typed edges). Smaller models tend to flatten
    # everything into a single chain.
    #
    # Primary:  github/gpt-5-chat — OpenAI's GPT-5 chat variant via GitHub
    #           Models. Smartest available without an Anthropic key (which
    #           we don't have — GitHub Models doesn't host Claude). Handles
    #           the 10-node-typed schema cleanly.
    # Fallback: github/gpt-4.1 — flagship 1M-context model. Used if gpt-5
    #           gets rate-limited.
    # Last:     github/gpt-4o — smaller, fastest fallback.
    #
    # NOTE: Operator preference is anthropic/claude-sonnet-4-5-20250929.
    # The moment an `ANTHROPIC_API_KEY` is added to the secrets vault, set
    # `FLOWVIZ_AI_PRIMARY_MODEL=anthropic/claude-sonnet-4-5-20250929` (and
    # `FLOWVIZ_AI_FALLBACK_MODELS=github/gpt-5-chat,github/gpt-4.1`) in the
    # same vault — the startup hook in main.py picks them up. Restarts only
    # flowviz; no code change needed.
    ai_primary_model: str = "github/gpt-4.1"
    ai_fallback_models: str = "github/gpt-5-chat,github/gpt-4o"


@lru_cache
def get_settings() -> Settings:
    return Settings()
