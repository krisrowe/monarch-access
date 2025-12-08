# Monarch Access

Lightweight CLI and Python SDK for accessing [Monarch Money](https://www.monarchmoney.com/) financial data.

```bash
monarch accounts
monarch net-worth
monarch transactions list --after 2025-01-01 --before 2025-12-31
```

## Installation

```bash
pip install git+https://github.com/krisrowe/monarch-access.git
```

Or clone and install locally:

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
pip install .
```

This installs the `monarch` command globally.

## Requirements

- Python 3.10+
- A Monarch Money account

## Authentication

Monarch Money doesn't have a public API, so you need to grab your session token from the browser:

1. Go to https://app.monarchmoney.com/ and log in
2. Open DevTools (F12) → Console tab
3. Paste and run:
   ```javascript
   JSON.parse(JSON.parse(localStorage.getItem("persist:root")).user).token
   ```
4. Copy the token string
5. Save it:
   ```bash
   monarch auth "YOUR_TOKEN_HERE"
   ```

The token is saved to `~/.config/monarch/token` and typically lasts several months. You'll need to repeat this when it expires.

## CLI Usage

All commands default to text format with ASCII tables. Use `--format json` or `--format csv` for machine-readable output.

### List Transactions

```bash
# Basic usage (requires both --after and --before)
monarch transactions list --after 2025-01-01 --before 2025-12-31

# Filter by account (supports wildcards)
monarch transactions list --after 2025-01-01 --before 2025-12-31 --account "Chase*"

# Filter by category (comma-separated)
monarch transactions list --after 2025-01-01 --before 2025-12-31 --category "Shopping,Groceries"

# Filter by merchant (supports wildcards)
monarch transactions list --after 2025-01-01 --before 2025-12-31 --merchant "*amazon*"

# Output as JSON or CSV
monarch transactions list --after 2025-01-01 --before 2025-12-31 --format json
monarch transactions list --after 2025-01-01 --before 2025-12-31 --format csv

# Limit results
monarch transactions list --after 2025-01-01 --before 2025-12-31 --limit 50
```

### List Accounts

```bash
monarch accounts
monarch accounts --format json
monarch accounts --format csv
```

### Net Worth Report

```bash
monarch net-worth
monarch net-worth --format json
monarch net-worth --format csv
```

Shows assets and liabilities grouped by category with totals.

## Python SDK Usage

```python
import asyncio
from monarch import MonarchClient

async def main():
    client = MonarchClient()

    # Get all accounts
    accounts = await client.get_accounts()

    # Get transactions
    transactions = await client.get_transactions(
        limit=100,
        start_date="2025-01-01",
        end_date="2025-12-31",
    )

    # Get categories
    categories = await client.get_categories()

asyncio.run(main())
```

## Project Structure

```
monarch-access/
├── pyproject.toml      # Package config and dependencies
└── monarch/            # SDK package
    ├── __init__.py
    ├── cli.py          # CLI entry point
    ├── client.py       # MonarchClient - auth & API requests
    ├── queries.py      # GraphQL queries
    ├── accounts.py     # Account formatting
    ├── transactions.py # Transaction formatting
    └── net_worth.py    # Net worth report logic & formatting

~/.config/monarch/token # Auth token (created by monarch auth)
```

## License

MIT
