from __future__ import annotations

import aiohttp

from app.config import API_BASE_URL


async def register_user(email: str, version: str) -> dict:
    url = f"{API_BASE_URL}/register"
    payload = {"email": email, "version": version}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=15) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_config() -> dict:
    url = f"{API_BASE_URL}/config"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as resp:
            resp.raise_for_status()
            return await resp.json()