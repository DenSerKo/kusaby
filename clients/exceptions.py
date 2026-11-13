from typing import Any


class SabyAPIError(Exception):
    """Ошибка, возвращённая API СБИС в JSON-RPC ответе."""

    def __init__(
        self,
        message: str,
        code: int | str | None = None,
        details: str | None = None,
        error_type: str | None = None,
        data: Any = None,
        http_status: int | None = None,
        method: str | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details
        self.error_type = error_type
        self.data = data
        self.http_status = http_status
        self.method = method

        super().__init__(message)


class SabyResponseError(Exception):
    """СБИС вернул ответ, который приложение не смогло обработать."""
