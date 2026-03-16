"""Recurring transaction utilities."""

import calendar
import csv
import io
from datetime import date
from typing import Any, Optional

from .queries import (
    MARK_AS_NOT_RECURRING_MUTATION,
    RECURRING_TRANSACTION_ITEMS_QUERY,
    UPDATE_MERCHANT_MUTATION,
)


async def _find_merchant_for_stream(client, stream_id: str) -> dict:
    """Look up the merchant and its current recurring state for a given stream_id.

    Uses Common_GetRecurringStreams (which includes inactive streams) to find
    the merchant, then queries the merchant for its current recurrence settings.
    """
    # Use the full stream list which includes inactive streams
    q = """query {
        recurringTransactionStreams(includePending: true, includeLiabilities: true) {
            stream {
                id
                merchant { id name }
            }
        }
    }"""
    data = await client._request(q, {})
    all_streams = data.get("recurringTransactionStreams", [])

    merchant_id = None
    merchant_name = None
    for item in all_streams:
        stream = item.get("stream", {})
        if stream.get("id") == stream_id:
            merchant = stream.get("merchant") or {}
            merchant_id = merchant.get("id")
            merchant_name = merchant.get("name")
            break

    if not merchant_id:
        raise Exception(f"Stream {stream_id} not found or has no merchant (may be a credit report liability)")

    # Get current merchant state
    q2 = """query($search: String) {
        merchants(search: $search) {
            id name
            recurringTransactionStream { id frequency amount baseDate isActive }
        }
    }"""
    data2 = await client._request(q2, {"search": merchant_name})
    for m in data2.get("merchants", []):
        if m["id"] == merchant_id:
            return m

    raise Exception(f"Merchant {merchant_id} ({merchant_name}) not found")


async def update_recurring(
    client,
    stream_id: str,
    *,
    status: str | None = None,
    amount: float | None = None,
    frequency: str | None = None,
) -> dict:
    """Update a recurring stream's settings via its merchant.

    Args:
        stream_id: The stream_id from list_recurring.
        status: 'active', 'inactive', or 'removed'.
            - active: reactivate a deactivated stream
            - inactive: deactivate (reversible, keeps in system)
            - removed: permanently remove all streams for this merchant
        amount: New recurring amount (negative for expenses).
        frequency: New frequency (monthly, biweekly, weekly, etc.).

    Returns the updated merchant data, or removal result.
    """
    if status == "removed":
        return await mark_as_not_recurring(client, stream_id)

    merchant = await _find_merchant_for_stream(client, stream_id)
    rts = merchant.get("recurringTransactionStream") or {}

    # Build recurrence object — must send all fields
    recurrence = {
        "isRecurring": True,
        "frequency": frequency if frequency is not None else rts.get("frequency", "monthly"),
        "baseDate": rts.get("baseDate", "2025-01-01"),
        "amount": amount if amount is not None else rts.get("amount", 0),
        "isActive": rts.get("isActive", True),
    }

    if status == "active":
        recurrence["isActive"] = True
    elif status == "inactive":
        recurrence["isActive"] = False

    variables = {
        "input": {
            "merchantId": merchant["id"],
            "name": merchant["name"],
            "recurrence": recurrence,
        }
    }

    data = await client._request(UPDATE_MERCHANT_MUTATION, variables)
    result = data.get("updateMerchant", {})
    return result.get("merchant", result)


async def mark_as_not_recurring(client, stream_id: str) -> dict:
    """Mark a recurring stream as not recurring.

    Removes the stream from Monarch's recurring list.
    Returns the mutation result.
    """
    variables = {"streamId": stream_id}
    data = await client._request(MARK_AS_NOT_RECURRING_MUTATION, variables)
    result = data.get("markStreamAsNotRecurring", {})
    errors = result.get("errors")
    if errors:
        msg = errors.get("message", "") if isinstance(errors, dict) else str(errors)
        raise Exception(f"Failed to mark stream as not recurring: {msg}")
    return result


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


def _trailing_year_range() -> tuple[str, str]:
    """Return (start_date, end_date) spanning 12 months back through current month."""
    today = date.today()
    start = today.replace(year=today.year - 1, day=1).isoformat()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day).isoformat()
    return start, end


def collapse_to_streams(items: list[dict]) -> list[dict]:
    """Collapse recurring items into one entry per stream.

    Takes the raw recurring transaction items (which are date-specific
    occurrences) and deduplicates by stream ID, producing a stable list
    of recurring obligations.

    For each stream, tracks:
    - Current month's occurrence (due_date, is_past, transaction_id)
    - Last paid date across all items (last_paid_date)
    """
    streams: dict[str, dict] = {}

    # Sort items by date so we process in chronological order
    sorted_items = sorted(items, key=lambda i: i.get("date", ""))

    for item in sorted_items:
        stream = item.get("stream", {})
        stream_id = stream.get("id")
        if not stream_id:
            continue

        is_paid = item.get("transactionId") is not None
        item_date = item.get("date", "")

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
                "due_date": item_date,
                "actual_amount": item.get("amount"),
                "transaction_id": item.get("transactionId"),
                "last_paid_date": item_date if is_paid else None,
            }
        else:
            existing = streams[stream_id]

            # Track last paid date across all occurrences
            if is_paid and (existing["last_paid_date"] is None or item_date > existing["last_paid_date"]):
                existing["last_paid_date"] = item_date

            # Most recent item becomes the current occurrence
            if item_date > existing["due_date"]:
                existing["is_past"] = item.get("isPast", False)
                existing["due_date"] = item_date
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

    col_widths = [24, 12, 10, 10, 10]
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

    rows = [("Merchant", "Amount", "Due Date", "Last Paid", "Status")]

    for s in streams:
        rows.append((
            s.get("merchant", "")[:24],
            fmt_money(s.get("amount")),
            s.get("due_date", "")[:10],
            (s.get("last_paid_date") or "never")[:10],
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
        "due_date", "last_paid_date", "is_past", "transaction_id", "stream_id",
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
            "due_date": s.get("due_date", ""),
            "last_paid_date": s.get("last_paid_date", ""),
            "is_past": s.get("is_past", False),
            "transaction_id": s.get("transaction_id", ""),
            "stream_id": s.get("stream_id", ""),
        })

    return output.getvalue()
