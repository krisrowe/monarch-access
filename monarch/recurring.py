"""Recurring transaction utilities."""

import csv
import io
from typing import Any, Optional

from .queries import RECURRING_TRANSACTION_ITEMS_QUERY


async def get_recurring_transaction_items(
    client,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Get recurring transaction items for a date range."""
    variables: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
    }

    data = await client._request(RECURRING_TRANSACTION_ITEMS_QUERY, variables)
    return data.get("recurringTransactionItems", [])


def format_text(items: list[dict]) -> str:
    """Format recurring items as ASCII text table."""
    if not items:
        return "No recurring items found."

    def fmt_money(amount) -> str:
        if amount is None:
            return ""
        amount = float(amount)
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    lines = []
    lines.append(f"RECURRING ITEMS ({len(items)})")

    col_widths = [10, 24, 20, 12, 8]
    alignments = ["l", "l", "l", "r", "l"]

    def make_table(rows: list[tuple]) -> list[str]:
        result = []
        separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        result.append(separator)
        for i, row in enumerate(rows):
            cells = []
            for val, width, align in zip(row, col_widths, alignments):
                text = str(val)[:width]
                if align == "r":
                    cells.append(f" {text:>{width}} ")
                else:
                    cells.append(f" {text:<{width}} ")
            result.append("|" + "|".join(cells) + "|")
            if i == 0:
                result.append(separator)
        result.append(separator)
        return result

    rows = [("Date", "Merchant", "Category", "Amount", "Status")]

    for item in items:
        date = item.get("date", "")
        stream = item.get("stream", {})
        merchant = (stream.get("merchant") or {}).get("name", "")
        category = (item.get("category") or {}).get("name", "")
        amount = item.get("amount") or stream.get("amount")
        is_past = item.get("isPast", False)
        has_txn = item.get("transactionId") is not None
        if has_txn:
            status = "Paid"
        elif is_past:
            status = "Overdue"
        else:
            status = "Upcoming"
        rows.append((date, merchant[:24], category[:20], fmt_money(amount), status))

    lines.extend(make_table(rows))

    # Summary
    total = sum(
        float(item.get("amount") or item.get("stream", {}).get("amount") or 0)
        for item in items
    )
    paid = sum(1 for item in items if item.get("transactionId"))
    lines.append("")
    lines.append(f"Total: {fmt_money(total)}  |  Paid: {paid}/{len(items)}")

    return "\n".join(lines)


def format_csv(items: list[dict]) -> str:
    """Format recurring items as CSV."""
    if not items:
        return ""

    output = io.StringIO()
    fieldnames = [
        "date", "merchant", "category", "account", "amount",
        "expected_amount", "frequency", "status", "transaction_id",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for item in items:
        stream = item.get("stream", {})
        is_past = item.get("isPast", False)
        has_txn = item.get("transactionId") is not None
        if has_txn:
            status = "paid"
        elif is_past:
            status = "overdue"
        else:
            status = "upcoming"

        writer.writerow({
            "date": item.get("date", ""),
            "merchant": (stream.get("merchant") or {}).get("name", ""),
            "category": (item.get("category") or {}).get("name", ""),
            "account": (item.get("account") or {}).get("displayName", ""),
            "amount": item.get("amount", ""),
            "expected_amount": stream.get("amount", ""),
            "frequency": stream.get("frequency", ""),
            "status": status,
            "transaction_id": item.get("transactionId", ""),
        })

    return output.getvalue()
