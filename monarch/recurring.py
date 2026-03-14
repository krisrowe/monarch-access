"""Recurring transaction utilities."""

import calendar
import csv
import io
from datetime import date
from typing import Any, Optional

from .queries import RECURRING_TRANSACTION_ITEMS_QUERY


async def get_recurring_transaction_items(
    client,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Get raw recurring transaction items for a date range."""
    variables: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
    }

    data = await client._request(RECURRING_TRANSACTION_ITEMS_QUERY, variables)
    return data.get("recurringTransactionItems", [])


def _current_month_range() -> tuple[str, str]:
    """Return (start_date, end_date) for the current month."""
    today = date.today()
    start = today.replace(day=1).isoformat()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day).isoformat()
    return start, end


def collapse_to_streams(items: list[dict]) -> list[dict]:
    """Collapse recurring items into one entry per stream.

    Takes the raw recurring transaction items (which are date-specific
    occurrences) and deduplicates by stream ID, producing a stable list
    of recurring obligations. Monarch's raw fields (isPast, transactionId)
    are preserved directly for the consumer to interpret.
    """
    streams: dict[str, dict] = {}

    for item in items:
        stream = item.get("stream", {})
        stream_id = stream.get("id")
        if not stream_id:
            continue

        if stream_id not in streams:
            merchant = stream.get("merchant") or {}
            streams[stream_id] = {
                "stream_id": stream_id,
                "merchant": merchant.get("name", ""),
                "merchant_id": merchant.get("id", ""),
                "amount": stream.get("amount"),
                "frequency": stream.get("frequency", ""),
                "is_approximate": stream.get("isApproximate", False),
                "category": (item.get("category") or {}).get("name", ""),
                "category_id": (item.get("category") or {}).get("id", ""),
                "account": (item.get("account") or {}).get("displayName", ""),
                "account_id": (item.get("account") or {}).get("id", ""),
                "is_past": item.get("isPast", False),
                "due_date": item.get("date", ""),
                "actual_amount": item.get("amount"),
                "transaction_id": item.get("transactionId"),
            }
        else:
            # If we already have this stream, prefer the most recent item
            existing = streams[stream_id]
            if item.get("date", "") > existing["due_date"]:
                existing["is_past"] = item.get("isPast", False)
                existing["due_date"] = item.get("date", "")
                existing["actual_amount"] = item.get("amount")
                existing["transaction_id"] = item.get("transactionId")

    # Sort by merchant name for stable output
    return sorted(streams.values(), key=lambda s: s.get("merchant", "").lower())


def _display_status(s: dict) -> str:
    """Human-readable status for text/CSV display."""
    if s.get("transaction_id") is not None:
        return "PAID"
    elif s.get("is_past"):
        return "OVERDUE"
    else:
        return "UPCOMING"


def format_text(streams: list[dict]) -> str:
    """Format collapsed stream list as ASCII text table."""
    if not streams:
        return "No recurring items found."

    def fmt_money(amount) -> str:
        if amount is None:
            return ""
        amount = float(amount)
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    lines = []
    lines.append(f"RECURRING ({len(streams)})")

    col_widths = [24, 12, 10, 20, 10]
    alignments = ["l", "r", "l", "l", "l"]

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

    rows = [("Merchant", "Amount", "Frequency", "Account", "Status")]

    for s in streams:
        rows.append((
            s.get("merchant", "")[:24],
            fmt_money(s.get("amount")),
            s.get("frequency", "")[:10],
            s.get("account", "")[:20],
            _display_status(s),
        ))

    lines.extend(make_table(rows))

    total = sum(float(s.get("amount") or 0) for s in streams)
    paid = sum(1 for s in streams if s.get("transaction_id") is not None)
    overdue = sum(1 for s in streams if s.get("is_past") and s.get("transaction_id") is None)
    upcoming = sum(1 for s in streams if not s.get("is_past") and s.get("transaction_id") is None)
    lines.append("")
    lines.append(f"Monthly total: {fmt_money(total)}  |  Paid: {paid}  Overdue: {overdue}  Upcoming: {upcoming}")

    return "\n".join(lines)


def format_csv(streams: list[dict]) -> str:
    """Format collapsed stream list as CSV."""
    if not streams:
        return ""

    output = io.StringIO()
    fieldnames = [
        "merchant", "amount", "frequency", "category", "account",
        "is_past", "due_date", "transaction_id", "stream_id",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for s in streams:
        writer.writerow({
            "merchant": s.get("merchant", ""),
            "amount": s.get("amount", ""),
            "frequency": s.get("frequency", ""),
            "category": s.get("category", ""),
            "account": s.get("account", ""),
            "is_past": s.get("is_past", False),
            "due_date": s.get("due_date", ""),
            "transaction_id": s.get("transaction_id", ""),
            "stream_id": s.get("stream_id", ""),
        })

    return output.getvalue()
