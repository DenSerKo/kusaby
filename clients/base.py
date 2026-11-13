from typing import Any

import httpx
from django.conf import settings

from clients.exceptions import SabyAPIError, SabyResponseError


class BaseClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url if base_url is not None else settings.SABY_API_BASE_URL
        self.token = token
        self.timeout = timeout
        self.headers = headers.copy() if headers else {}
        if self.token:
            self.headers["X-SBISSessionID"] = self.token
        self.headers.setdefault("Content-Type", "application/json; charset=utf-8")
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

    async def _request_response(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict | None = None,
        json: dict | list | None = None,
        data: Any = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("Используйте API клиент внутри 'async with'")

        return await self._client.request(
            method, endpoint, params=params, json=json, data=data, **kwargs
        )

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
        response = await self._request_response(
            method, endpoint, params=params, json=json, data=data, **kwargs
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
        request_id: int = 0,
    ) -> dict[str, Any]:
        response = await self._request_response(
            "POST",
            endpoint,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": request_id,
            },
        )

        try:
            data = response.json() if response.content else None
        except ValueError as exc:
            response.raise_for_status()
            raise SabyResponseError("СБИС вернул некорректный JSON") from exc

        error = self._parse_jsonrpc_error(data, method, response.status_code)
        if error:
            raise error

        response.raise_for_status()

        if not isinstance(data, dict):
            raise SabyResponseError("Ожидался объект в ответе JSON-RPC")
        return data

    @staticmethod
    def _parse_jsonrpc_error(
        response: Any,
        method: str,
        http_status: int | None = None,
    ) -> SabyAPIError | None:
        if not isinstance(response, dict):
            return None
        error = response.get("error")
        if not isinstance(error, dict):
            return None
        return SabyAPIError(
            code=error.get("code"),
            message=error.get("message") or "Неизвестная ошибка СБИС",
            details=error.get("details"),
            error_type=error.get("type"),
            data=error.get("data"),
            http_status=http_status,
            method=method,
        )

    async def get(self, endpoint: str, *, params: dict | None = None, **kwargs: Any):
        return await self._request("GET", endpoint, params=params, **kwargs)

    async def post(
        self, endpoint: str, *, json: dict | list | None = None,
        data: Any = None, params: dict | None = None, **kwargs: Any,
    ):
        return await self._request(
            "POST", endpoint, json=json, data=data, params=params, **kwargs
        )

    async def put(
        self, endpoint: str, *, json: dict | list | None = None,
        data: Any = None, params: dict | None = None, **kwargs: Any,
    ):
        return await self._request(
            "PUT", endpoint, json=json, data=data, params=params, **kwargs
        )

    async def patch(
        self, endpoint: str, *, json: dict | list | None = None,
        data: Any = None, params: dict | None = None, **kwargs: Any,
    ):
        return await self._request(
            "PATCH", endpoint, json=json, data=data, params=params, **kwargs
        )

    async def delete(self, endpoint: str, *, params: dict | None = None, **kwargs: Any):
        return await self._request("DELETE", endpoint, params=params, **kwargs)
