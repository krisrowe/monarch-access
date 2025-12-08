#!/usr/bin/env python3
"""Monarch Money CLI."""

import asyncio
import fnmatch
import json
import sys
from typing import Optional

import click

from . import accounts, categories, net_worth, transactions
from .transactions import get as txn_get, list as txn_list, update as txn_update
from .client import MonarchClient, AuthenticationError, APIError


def run_async(coro):
    """Run async function in sync context."""
    return asyncio.run(coro)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Monarch Money CLI - Access your financial data."""
    pass


@cli.group("transactions")
def transactions_group():
    """Transaction commands."""
    pass


@transactions_group.command("list")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format")
@click.option("--account", multiple=True, help="Filter by account name (comma-separated or multiple flags)")
@click.option("--category", multiple=True, help="Filter by category name (comma-separated or multiple flags)")
@click.option("--start", "start_date", help="Start date, inclusive (YYYY-MM-DD)")
@click.option("--end", "end_date", help="End date, inclusive (YYYY-MM-DD)")
@click.option("--merchant", help="Filter by merchant name (supports * wildcards)")
@click.option("--notes", help="Filter by notes content (supports * wildcards)")
@click.option("--original-statement", "original_statement", help="Filter by original statement (supports * wildcards)")
@click.option("--limit", default=1000, help="Max transactions to fetch")
def list_transactions(
    output_format: str,
    account: tuple,
    category: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    original_statement: Optional[str],
    limit: int,
):
    """List transactions with optional filters."""
    try:
        result = run_async(_list_transactions(
            output_format, account, category, start_date, end_date,
            merchant, notes, original_statement, limit
        ))
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


async def _list_transactions(
    output_format: str,
    account: tuple,
    category: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    original_statement: Optional[str],
    limit: int,
) -> str:
    """Async implementation of list transactions."""
    client = MonarchClient()

    # Parse comma-separated values from options
    account_names = _parse_multi_option(account)
    category_names = _parse_multi_option(category)

    # Get account IDs if filtering by account name
    account_ids = None
    if account_names:
        accts = await accounts.get_accounts(client)
        account_ids = [
            a["id"] for a in accts
            if any(fnmatch.fnmatch(a["displayName"].lower(), name.lower()) for name in account_names)
        ]
        if not account_ids:
            return json.dumps({"error": f"No accounts matching: {account_names}"})

    # Get category IDs if filtering by category name
    category_ids = None
    if category_names:
        cats = await categories.get_categories(client)
        category_ids = [
            c["id"] for c in cats
            if any(fnmatch.fnmatch(c["name"].lower(), name.lower()) for name in category_names)
        ]
        if not category_ids:
            return json.dumps({"error": f"No categories matching: {category_names}"})

    # Fetch transactions
    data = await txn_list.get_transactions(
        client,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        account_ids=account_ids,
        category_ids=category_ids,
    )

    txns = data.get("results", [])
    total_count = data.get("totalCount", 0)

    # Apply client-side filters (merchant, notes, original_statement)
    if merchant:
        txns = [t for t in txns if _wildcard_match(t.get("merchant", {}).get("name", ""), merchant)]
    if notes:
        txns = [t for t in txns if _wildcard_match(t.get("notes") or "", notes)]
    if original_statement:
        txns = [t for t in txns if _wildcard_match(t.get("plaidName") or "", original_statement)]

    # Check if there are more results than returned
    truncated = total_count > limit

    # Format output
    if output_format == "json":
        result = {"transactions": txns, "count": len(txns), "total": total_count}
        if truncated:
            result["truncated"] = True
            result["message"] = f"Showing {limit} of {total_count} transactions. Use --limit to fetch more."
        return json.dumps(result, indent=2, default=str)
    elif output_format == "csv":
        output = transactions.format_csv(txns)
        if truncated:
            output += f"\n# Showing {limit} of {total_count} transactions. Use --limit to fetch more.\n"
        return output
    else:
        output = transactions.format_text(txns)
        if truncated:
            output += f"\n\n(Showing {limit} of {total_count} transactions. Use --limit to fetch more.)"
        return output


def _parse_multi_option(values: tuple) -> list[str]:
    """Parse comma-separated values from multiple option flags."""
    result = []
    for val in values:
        result.extend([v.strip() for v in val.split(",") if v.strip()])
    return result


def _wildcard_match(text: str, pattern: str) -> bool:
    """Match text against pattern with * wildcard support."""
    return fnmatch.fnmatch(text.lower(), pattern.lower())


@transactions_group.command("get")
@click.argument("transaction_id")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def get_transaction(transaction_id: str, output_format: str):
    """Get a single transaction by ID."""
    try:
        result = run_async(_get_transaction(transaction_id, output_format))
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


async def _get_transaction(transaction_id: str, output_format: str) -> str:
    """Async implementation of get transaction."""
    client = MonarchClient()
    txn = await txn_get.get_transaction(client, transaction_id)

    if not txn:
        return json.dumps({"error": f"Transaction not found: {transaction_id}"})

    if output_format == "json":
        return json.dumps(txn, indent=2, default=str)
    else:
        return transactions.format_single_text(txn)


@transactions_group.command("update")
@click.argument("transaction_id")
@click.option("--category", help="Category name to set")
@click.option("--merchant", help="Merchant name to set")
@click.option("--notes", help="Notes to set (use empty string to clear)")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def update_transaction(
    transaction_id: str,
    category: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    output_format: str,
):
    """Update a transaction by ID. Only specified fields are changed."""
    try:
        result = run_async(_update_transaction(
            transaction_id, category, merchant, notes, output_format
        ))
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


async def _update_transaction(
    transaction_id: str,
    category: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    output_format: str,
) -> str:
    """Async implementation of update transaction."""
    client = MonarchClient()

    # Resolve category name to ID if provided
    category_id = None
    if category is not None:
        cats = await categories.get_categories(client)
        matching = [c for c in cats if c["name"].lower() == category.lower()]
        if not matching:
            # Try partial match
            matching = [c for c in cats if category.lower() in c["name"].lower()]
        if not matching:
            return json.dumps({"error": f"Category not found: {category}"})
        category_id = matching[0]["id"]

    # Perform update
    updated = await txn_update.update_transaction(
        client,
        transaction_id=transaction_id,
        category_id=category_id,
        merchant_name=merchant,
        notes=notes,
    )

    # Format output
    if output_format == "json":
        return json.dumps(updated, indent=2, default=str)
    else:
        return transactions.format_single_text(updated)


@cli.command("accounts")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format")
def list_accounts(output_format: str):
    """List all accounts."""
    try:
        result = run_async(_list_accounts(output_format))
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


async def _list_accounts(output_format: str) -> str:
    """Async implementation of list accounts."""
    client = MonarchClient()
    accts = await accounts.get_accounts(client)

    if output_format == "json":
        return json.dumps(accts, indent=2, default=str)
    elif output_format == "csv":
        return accounts.format_csv(accts)
    else:
        return accounts.format_text(accts)


@cli.command("auth")
@click.argument("token")
def auth(token: str):
    """Save authentication token."""
    client = MonarchClient(token=token)
    client.save_token()
    click.echo(f"Token saved to {client._token_file}")


@cli.command("net-worth")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format")
def net_worth_cmd(output_format: str):
    """Show net worth report with assets and liabilities."""
    try:
        result = run_async(_net_worth(output_format))
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


async def _net_worth(output_format: str) -> str:
    client = MonarchClient()
    accts = await accounts.get_accounts(client)
    report = net_worth.build_report(accts)

    if output_format == "json":
        return json.dumps(report, indent=2)
    elif output_format == "csv":
        return net_worth.format_csv(report)
    else:
        return net_worth.format_text(report)


if __name__ == "__main__":
    cli()
