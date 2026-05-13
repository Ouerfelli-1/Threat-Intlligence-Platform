import httpx


def build_default_timeout(connect: float = 10.0, read: float = 30.0) -> httpx.Timeout:
    return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)


class ResilientClient:
    """Lightly-wrapped httpx.AsyncClient with sane defaults for outbound calls."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    def __getattr__(self, name: str):
        """Proxy any unknown attribute (get, post, put, delete, etc.) to the inner httpx client."""
        return getattr(self._client, name)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ResilientClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


def build_resilient_client(
    *,
    headers: dict[str, str] | None = None,
    base_url: str | None = None,
    timeout: httpx.Timeout | None = None,
    follow_redirects: bool = True,
) -> ResilientClient:
    client = httpx.AsyncClient(
        headers=headers or {},
        base_url=base_url or "",
        timeout=timeout or build_default_timeout(),
        follow_redirects=follow_redirects,
        http2=False,
    )
    return ResilientClient(client)
