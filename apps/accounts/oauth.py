import httpx
from django.conf import settings


async def exchange_code_for_token(code: str) -> str:
    """Exchange a short-lived Saby authorization code for an access token."""
    if not settings.SABY_CLIENT_ID or not settings.SABY_CLIENT_SECRET:
        raise ValueError("Не настроены параметры OAuth приложения Saby.")

    payload = {
        "code": code,
        "client_id": settings.SABY_CLIENT_ID,
        "client_secret": settings.SABY_CLIENT_SECRET,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            settings.SABY_OAUTH_TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError("Saby вернул некорректный JSON при обмене code.") from exc

    access_token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("В ответе Saby отсутствует access_token.")

    return access_token
