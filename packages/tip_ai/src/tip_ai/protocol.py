from typing import Any, Protocol


class ContextProvider(Protocol):
    """Provides AI synthesis context. Implementations live OUTSIDE tip_ai (e.g. in services)."""

    async def company_profile(self) -> dict[str, Any]: ...
    async def related_actors(self, item: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def related_iocs(self, item: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def related_articles(self, item: dict[str, Any]) -> list[dict[str, Any]]: ...


class NullContextProvider:
    """Returns empty context. Useful for unit tests and bootstrap."""

    async def company_profile(self) -> dict[str, Any]:
        return {}

    async def related_actors(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def related_iocs(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def related_articles(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        return []
