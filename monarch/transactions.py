"""Transaction formatting utilities."""

import csv
import io


def format_csv(transactions: list[dict]) -> str:
    """Format transactions as CSV."""
    if not transactions:
        return ""

    output = io.StringIO()
    fieldnames = ["date", "account", "merchant", "category", "amount", "notes", "original_statement"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for t in transactions:
        writer.writerow({
            "date": t.get("date", ""),
            "account": t.get("account", {}).get("displayName", ""),
            "merchant": t.get("merchant", {}).get("name", ""),
            "category": t.get("category", {}).get("name", ""),
            "amount": t.get("amount", 0),
            "notes": t.get("notes", ""),
            "original_statement": t.get("plaidName", ""),
        })

    return output.getvalue()


def format_text(transactions: list[dict]) -> str:
    """Format transactions as ASCII text with table."""
    if not transactions:
        return "No transactions found."

    def fmt_money(amount: float) -> str:
        if amount is None:
            return "$0.00"
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    lines = []
    lines.append(f"Transactions ({len(transactions)})")
    lines.append("=" * 85)
    lines.append("")

    col_widths = [10, 24, 20, 12]
    alignments = ["l", "l", "l", "r"]

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

    rows = [("Date", "Merchant", "Category", "Amount")]

    for t in transactions:
        date = t.get("date", "")
        merchant = (t.get("merchant") or {}).get("name", "") or t.get("plaidName", "")[:24]
        category = (t.get("category") or {}).get("name", "")
        amount = t.get("amount", 0) or 0
        rows.append((date, merchant[:24], category[:20], fmt_money(amount)))

    lines.extend(make_table(rows))

    total = sum(t.get("amount", 0) or 0 for t in transactions)
    lines.append("")
    lines.append(f"Total: {fmt_money(total)}")

    return "\n".join(lines)
