"""Monarch Money API client."""

import os
from pathlib import Path
from typing import Any, Optional

import aiohttp

from .queries import ACCOUNTS_QUERY, TRANSACTIONS_QUERY, TRANSACTION_CATEGORIES_QUERY

DEFAULT_TOKEN_FILE = Path.home() / ".config" / "monarch" / "token"
GRAPHQL_URL = "https://api.monarchmoney.com/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://app.monarchmoney.com",
    "Referer": "https://app.monarchmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class MonarchClientError(Exception):
    """Base exception for Monarch client errors."""
    pass


class AuthenticationError(MonarchClientError):
    """Raised when authentication fails."""
    pass


class APIError(MonarchClientError):
    """Raised when API request fails."""
    pass


class MonarchClient:
    """Lightweight client for Monarch Money API."""

    def __init__(
        self,
        token: Optional[str] = None,
        token_file: Path = DEFAULT_TOKEN_FILE,
    ):
        self._token_file = token_file
        self._token = token

        if not self._token:
            self._load_token()

    def _load_token(self) -> None:
        """Load token from file."""
        try:
            self._token = self._token_file.read_text().strip()
        except FileNotFoundError:
            pass

    def save_token(self) -> None:
        """Save token to file."""
        if not self._token:
            raise AuthenticationError("No token to save")

        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        self._token_file.write_text(self._token)

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    async def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        if not self._token:
            raise AuthenticationError(
                "Not authenticated. Get token from browser:\n"
                "1. Login to https://app.monarchmoney.com/\n"
                "2. DevTools (F12) -> Console\n"
                "3. Run: JSON.parse(JSON.parse(localStorage.getItem('persist:root')).user).token"
            )

        headers = {**HEADERS, "Authorization": f"Token {self._token}"}
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(GRAPHQL_URL, json=payload, headers=headers) as resp:
                if resp.status == 401:
                    raise AuthenticationError("Invalid or expired token")
                if resp.status != 200:
                    text = await resp.text()
                    raise APIError(f"HTTP {resp.status}: {text[:200]}")

                data = await resp.json()
                if "errors" in data:
                    raise APIError(f"GraphQL error: {data['errors']}")

                return data.get("data", {})

    async def get_accounts(self) -> list[dict]:
        """Get all accounts."""
        data = await self._request(ACCOUNTS_QUERY)
        return data.get("accounts", [])

    async def get_transactions(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        account_ids: Optional[list[str]] = None,
        category_ids: Optional[list[str]] = None,
        search: Optional[str] = None,
    ) -> dict:
        """Get transactions with optional filters."""
        variables: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "filters": {
                "accounts": account_ids or [],
                "categories": category_ids or [],
            }
        }

        if search:
            variables["filters"]["search"] = search

        # Add date filters if provided
        if start_date:
            variables["filters"]["startDate"] = start_date
        if end_date:
            variables["filters"]["endDate"] = end_date

        data = await self._request(TRANSACTIONS_QUERY, variables)
        return data.get("allTransactions", {"totalCount": 0, "results": []})

    async def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        data = await self._request(TRANSACTION_CATEGORIES_QUERY)
        return data.get("categories", [])
