"""Category operations."""

from .queries import TRANSACTION_CATEGORIES_QUERY


async def get_categories(client) -> list[dict]:
    """Get all transaction categories."""
    data = await client._request(TRANSACTION_CATEGORIES_QUERY)
    return data.get("categories", [])
