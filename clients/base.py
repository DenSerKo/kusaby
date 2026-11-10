from typing import Any

import httpx
from django.conf import settings


class BaseClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or getattr(settings, "SABY_API_BASE_URL", "")
        self.token = token
        self.timeout = timeout

        self.headers = headers.copy() if headers else {}
        if self.token:
            self.headers["X-SBISSessionID"] = self.token
        self.headers["Content-Type"] = "application/json; charset=utf-8"

        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict | None = None,
        json: dict | list | None = None,
        data: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any] | None:
        if self._client is None:
            raise RuntimeError("Используйте API клиент внутри 'async with'")

        response = await self._client.request(
            method,
            endpoint,
            params=params,
            json=json,
            data=data,
            **kwargs,
        )
        response.raise_for_status()

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def jsonrpc(
            self,
            endpoint: str,
            method: str,
            params: dict,
            request_id: int = 0
    ) -> dict:
        response = await self.post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": request_id,
            },
        )

        if not isinstance(response, dict):
            raise ValueError("Ожидался объект в ответе JSON-RPC")

        return response

    async def get(self, endpoint: str, *, params: dict | None = None, **kwargs: Any):
        return await self._request("GET", endpoint, params=params, **kwargs)

    async def post(
        self,
        endpoint: str,
        *,
        json: dict | list | None = None,
        data: Any = None,
        params: dict | None = None,
        **kwargs: Any,
    ):
        return await self._request(
            "POST",
            endpoint,
            json=json,
            data=data,
            params=params,
            **kwargs,
        )

    async def put(
        self,
        endpoint: str,
        *,
        json: dict | list | None = None,
        data: Any = None,
        params: dict | None = None,
        **kwargs: Any,
    ):
        return await self._request(
            "PUT",
            endpoint,
            json=json,
            data=data,
            params=params,
            **kwargs,
        )

    async def patch(
        self,
        endpoint: str,
        *,
        json: dict | list | None = None,
        data: Any = None,
        params: dict | None = None,
        **kwargs: Any,
    ):
        return await self._request(
            "PATCH",
            endpoint,
            json=json,
            data=data,
            params=params,
            **kwargs,
        )

    async def delete(self, endpoint: str, *, params: dict | None = None, **kwargs: Any):
        return await self._request("DELETE", endpoint, params=params, **kwargs)