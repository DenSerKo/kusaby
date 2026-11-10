from .client import AuthClient


async def login_to_saby(username: str, password: str) -> dict:
    async with AuthClient() as client:
        return await client.login(username, password)


async def logout_from_saby(token: str) -> None:
    async with AuthClient(token=token) as client:
        await client.logout()
