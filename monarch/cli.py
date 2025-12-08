#!/usr/bin/env python3
"""Monarch Money CLI."""

import asyncio
import fnmatch
import json
import sys
from typing import Optional

import click

from . import accounts, net_worth, transactions
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
@click.option("--after", "after_date", help="Include transactions on or after this date (YYYY-MM-DD)")
@click.option("--before", "before_date", help="Exclude transactions on or after this date (YYYY-MM-DD)")
@click.option("--merchant", help="Filter by merchant name (supports * wildcards)")
@click.option("--notes", help="Filter by notes content (supports * wildcards)")
@click.option("--original-statement", "original_statement", help="Filter by original statement (supports * wildcards)")
@click.option("--limit", default=1000, help="Max transactions to fetch")
def list_transactions(
    output_format: str,
    account: tuple,
    category: tuple,
    after_date: Optional[str],
    before_date: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    original_statement: Optional[str],
    limit: int,
):
    """List transactions with optional filters."""
    try:
        result = run_async(_list_transactions(
            output_format, account, category, after_date, before_date,
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
    after_date: Optional[str],
    before_date: Optional[str],
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
        accounts = await client.get_accounts()
        account_ids = [
            a["id"] for a in accounts
            if any(fnmatch.fnmatch(a["displayName"].lower(), name.lower()) for name in account_names)
        ]
        if not account_ids:
            return json.dumps({"error": f"No accounts matching: {account_names}"})

    # Get category IDs if filtering by category name
    category_ids = None
    if category_names:
        categories = await client.get_categories()
        category_ids = [
            c["id"] for c in categories
            if any(fnmatch.fnmatch(c["name"].lower(), name.lower()) for name in category_names)
        ]
        if not category_ids:
            return json.dumps({"error": f"No categories matching: {category_names}"})

    # Fetch transactions
    data = await client.get_transactions(
        limit=limit,
        start_date=after_date,
        end_date=before_date,
        account_ids=account_ids,
        category_ids=category_ids,
    )

    txns = data.get("results", [])

    # Apply client-side filters (merchant, notes, original_statement)
    if merchant:
        txns = [t for t in txns if _wildcard_match(t.get("merchant", {}).get("name", ""), merchant)]
    if notes:
        txns = [t for t in txns if _wildcard_match(t.get("notes") or "", notes)]
    if original_statement:
        txns = [t for t in txns if _wildcard_match(t.get("plaidName") or "", original_statement)]

    # Format output
    if output_format == "json":
        return json.dumps(txns, indent=2, default=str)
    elif output_format == "csv":
        return transactions.format_csv(txns)
    else:
        return transactions.format_text(txns)


def _parse_multi_option(values: tuple) -> list[str]:
    """Parse comma-separated values from multiple option flags."""
    result = []
    for val in values:
        result.extend([v.strip() for v in val.split(",") if v.strip()])
    return result


def _wildcard_match(text: str, pattern: str) -> bool:
    """Match text against pattern with * wildcard support."""
    return fnmatch.fnmatch(text.lower(), pattern.lower())


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
    accts = await client.get_accounts()

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
    accounts = await client.get_accounts()
    report = net_worth.build_report(accounts)

    if output_format == "json":
        return json.dumps(report, indent=2)
    elif output_format == "csv":
        return net_worth.format_csv(report)
    else:
        return net_worth.format_text(report)


if __name__ == "__main__":
    cli()
