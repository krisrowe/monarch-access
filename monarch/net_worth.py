"""Net worth report generation."""

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta


def get_sync_status(account: dict) -> str:
    """Determine sync status from account fields."""
    if account.get("isManual"):
        return "manual"
    if account.get("syncDisabled"):
        return "disabled"

    credential = account.get("credential") or {}
    if credential.get("disconnectedFromDataProviderAt"):
        return "disconnected"
    if credential.get("updateRequired"):
        return "update_required"

    last_updated = account.get("displayLastUpdatedAt")
    if last_updated:
        try:
            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            now = datetime.now(updated_dt.tzinfo)
            if now - updated_dt > timedelta(days=7):
                return "stale"
            elif now - updated_dt > timedelta(days=1):
                return "recent"
            else:
                return "current"
        except (ValueError, TypeError):
            return "unknown"
    return "unknown"


def build_report(accounts: list) -> dict:
    """Build structured net worth report from accounts data."""
    nw_accounts = [a for a in accounts if a.get("includeInNetWorth", True)]

    assets_by_category = defaultdict(list)
    liabilities_by_category = defaultdict(list)

    for acc in nw_accounts:
        is_asset = acc.get("isAsset", True)
        acc_type = acc.get("type", {}).get("display", "Other")
        balance = acc.get("currentBalance", 0) or 0

        account_entry = {
            "name": acc.get("displayName", "Unknown"),
            "mask": acc.get("mask"),
            "balance": round(balance, 2),
            "institution": (acc.get("institution") or {}).get("name"),
            "subtype": (acc.get("subtype") or {}).get("display"),
            "sync_status": get_sync_status(acc),
            "last_updated": acc.get("displayLastUpdatedAt"),
        }

        if is_asset:
            assets_by_category[acc_type].append(account_entry)
        else:
            liabilities_by_category[acc_type].append(account_entry)

    def build_categories(grouped: dict) -> list:
        categories = []
        for cat_name, accts in sorted(grouped.items()):
            cat_total = sum(a["balance"] for a in accts)
            categories.append({
                "category": cat_name,
                "total": round(cat_total, 2),
                "accounts": sorted(accts, key=lambda x: -abs(x["balance"]))
            })
        return sorted(categories, key=lambda x: -abs(x["total"]))

    asset_categories = build_categories(assets_by_category)
    liability_categories = build_categories(liabilities_by_category)

    assets_total = sum(c["total"] for c in asset_categories)
    liabilities_total = sum(abs(c["total"]) for c in liability_categories)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "net_worth": round(assets_total - liabilities_total, 2),
        "assets": {
            "total": round(assets_total, 2),
            "categories": asset_categories
        },
        "liabilities": {
            "total": round(liabilities_total, 2),
            "categories": liability_categories
        }
    }


def format_csv(report: dict) -> str:
    """Format net worth report as CSV."""
    output = io.StringIO()
    fieldnames = ["section", "category", "account", "institution", "balance", "sync_status"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for section, label in [("assets", "Asset"), ("liabilities", "Liability")]:
        for cat in report[section]["categories"]:
            for acc in cat["accounts"]:
                writer.writerow({
                    "section": label,
                    "category": cat["category"],
                    "account": acc["name"],
                    "institution": acc.get("institution") or "",
                    "balance": acc["balance"],
                    "sync_status": acc.get("sync_status", ""),
                })

    return output.getvalue()


def format_text(report: dict) -> str:
    """Format net worth report as ASCII text with tables."""
    lines = []

    def fmt_money(amount: float) -> str:
        """Format amount as currency string."""
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    def make_table(rows: list[tuple], col_widths: list[int], alignments: list[str]) -> list[str]:
        """Create ASCII table rows. alignments: 'l' for left, 'r' for right."""
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

    # Header
    lines.append(f"Net Worth Report - {report['date']}")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append(f"NET WORTH: {fmt_money(report['net_worth'])}")
    lines.append(f"  Assets:      {fmt_money(report['assets']['total'])}")
    lines.append(f"  Liabilities: {fmt_money(report['liabilities']['total'])}")
    lines.append("")

    # Assets table
    if report["assets"]["categories"]:
        lines.append("ASSETS")
        lines.append("-" * 60)

        col_widths = [30, 20, 14]
        alignments = ["l", "l", "r"]
        rows = [("Account", "Institution", "Balance")]

        for cat in report["assets"]["categories"]:
            rows.append((f"[{cat['category']}]", "", fmt_money(cat["total"])))
            for acc in cat["accounts"]:
                inst = acc.get("institution") or ""
                rows.append((f"  {acc['name']}", inst[:20], fmt_money(acc["balance"])))

        lines.extend(make_table(rows, col_widths, alignments))
        lines.append("")

    # Liabilities table
    if report["liabilities"]["categories"]:
        lines.append("LIABILITIES")
        lines.append("-" * 60)

        col_widths = [30, 20, 14]
        alignments = ["l", "l", "r"]
        rows = [("Account", "Institution", "Balance")]

        for cat in report["liabilities"]["categories"]:
            rows.append((f"[{cat['category']}]", "", fmt_money(cat["total"])))
            for acc in cat["accounts"]:
                inst = acc.get("institution") or ""
                rows.append((f"  {acc['name']}", inst[:20], fmt_money(acc["balance"])))

        lines.extend(make_table(rows, col_widths, alignments))

    return "\n".join(lines)
