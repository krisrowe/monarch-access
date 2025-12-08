"""Get single transaction."""

from typing import Optional

from ..queries import GET_TRANSACTION_QUERY
from .common import fmt_money


async def get_transaction(client, transaction_id: str) -> Optional[dict]:
    """Get a single transaction by ID."""
    data = await client._request(GET_TRANSACTION_QUERY, {"id": transaction_id})
    return data.get("getTransaction")


def format_text(t: dict) -> str:
    """Format a single transaction as text with all fields."""
    lines = []
    lines.append("TRANSACTION")
    lines.append("-" * 40)
    lines.append(f"ID:          {t.get('id', '')}")
    lines.append(f"Date:        {t.get('date', '')}")
    lines.append(f"Amount:      {fmt_money(t.get('amount', 0))}")
    lines.append(f"Merchant:    {(t.get('merchant') or {}).get('name', '')}")
    lines.append(f"Category:    {(t.get('category') or {}).get('name', '')}")
    lines.append(f"Account:     {(t.get('account') or {}).get('displayName', '')}")
    lines.append(f"Notes:       {t.get('notes') or ''}")
    lines.append(f"Original:    {t.get('plaidName') or ''}")
    lines.append(f"Pending:     {t.get('pending', False)}")
    lines.append(f"Recurring:   {t.get('isRecurring', False)}")
    lines.append(f"Hidden:      {t.get('hideFromReports', False)}")
    lines.append(f"Needs Review:{t.get('needsReview', False)}")

    tags = t.get("tags") or []
    if tags:
        tag_names = ", ".join(tag.get("name", "") for tag in tags)
        lines.append(f"Tags:        {tag_names}")

    return "\n".join(lines)
