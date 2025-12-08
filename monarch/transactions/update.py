"""Update transaction."""

from typing import Any, Optional

from ..queries import UPDATE_TRANSACTION_MUTATION
from ..client import APIError


async def update_transaction(
    client,
    transaction_id: str,
    category_id: Optional[str] = None,
    merchant_name: Optional[str] = None,
    notes: Optional[str] = None,
    amount: Optional[float] = None,
    date: Optional[str] = None,
    hide_from_reports: Optional[bool] = None,
    needs_review: Optional[bool] = None,
) -> dict:
    """Update a transaction. Only provided fields are updated."""
    variables: dict[str, Any] = {
        "input": {
            "id": transaction_id,
        }
    }

    # category and merchant can be empty string to clear, or None to skip
    if category_id is not None:
        variables["input"]["category"] = category_id
    if merchant_name is not None:
        variables["input"]["name"] = merchant_name
    if notes is not None:
        variables["input"]["notes"] = notes
    if amount is not None:
        variables["input"]["amount"] = amount
    if date is not None:
        variables["input"]["date"] = date
    if hide_from_reports is not None:
        variables["input"]["hideFromReports"] = hide_from_reports
    if needs_review is not None:
        variables["input"]["needsReview"] = needs_review

    data = await client._request(UPDATE_TRANSACTION_MUTATION, variables)
    result = data.get("updateTransaction", {})

    if result.get("errors"):
        errors = result["errors"]
        msg = errors.get("message") or str(errors.get("fieldErrors", []))
        raise APIError(f"Update failed: {msg}")

    return result.get("transaction", {})
