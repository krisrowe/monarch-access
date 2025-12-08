# Contributing

## Project Structure

```
monarch-access/
├── pyproject.toml        # Package config and dependencies
└── monarch/              # SDK package
    ├── __init__.py
    ├── cli.py            # CLI entry point
    ├── client.py         # MonarchClient - auth & API requests
    ├── queries.py        # GraphQL queries
    ├── accounts.py       # Account operations & formatting
    ├── categories.py     # Category operations
    ├── net_worth.py      # Net worth report logic & formatting
    └── transactions/     # Transaction operations
        ├── list.py       # List transactions
        ├── get.py        # Get single transaction
        └── update.py     # Update transaction

~/.config/monarch/token   # Auth token (created by monarch auth)
```

## Architecture

- **`client.py`**: Only handles authentication (token load/save) and the generic `_request()` method for GraphQL calls
- **Operation modules** (accounts.py, categories.py, transactions/*.py): Each contains the API call function and any formatting utilities for that operation
- **`cli.py`**: Thin layer that wires up Click commands to the operation modules

## Development Setup

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
pip install -e .
```

The `-e` flag installs in editable mode so changes take effect immediately.
