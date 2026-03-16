# Contributing

## Project Structure

```
monarch-access/
├── pyproject.toml        # Package config, dependencies, entry points
├── Makefile              # Development commands
├── monarch/              # SDK package
│   ├── cli.py            # CLI entry point (monarch command)
│   ├── client.py         # MonarchClient - auth & API requests
│   ├── config.py         # Config/token path management
│   ├── queries.py        # GraphQL queries
│   ├── accounts.py       # Account operations & formatting
│   ├── categories.py     # Category operations
│   ├── net_worth.py      # Net worth report logic & formatting
│   ├── transactions/     # Transaction operations
│   │   ├── list.py
│   │   ├── get.py
│   │   └── update.py
│   ├── providers/        # Provider abstraction for API/local switching
│   │   ├── base.py       # Protocol interfaces
│   │   ├── api/          # Real Monarch API provider
│   │   └── local/        # Local TinyDB provider (for testing)
│   └── mcp/              # MCP server
│       └── server.py     # MCP server entry point (monarch-mcp command)
├── tests/
│   ├── conftest.py       # Pytest fixtures
│   ├── fixtures/
│   │   └── test_data_seed.json  # Seed data for test generation
│   ├── test_*.py         # Unit tests (use local provider)
│   └── integration/      # Integration tests (require live credentials)
│       └── test_live_reads.py

~/.config/monarch/token   # Auth token (created by monarch auth)
```

## Development

After cloning, just run tests - venv is created automatically:

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
make test
```

### Make Commands

| Command | Description |
|---------|-------------|
| `make test` | Run unit tests (auto-creates venv, no credentials needed) |
| `make integration-test` | Run integration tests (requires Monarch token) |
| `make install` | Install CLI + MCP server with pipx |
| `make clean` | Remove venv and build artifacts |
| `make uninstall` | Remove from pipx |

### Testing

**Unit tests** use a local provider with TinyDB - no network or auth required. Test data is auto-generated from `tests/fixtures/test_data_seed.json`.

**Integration tests** hit the live Monarch API and are skipped automatically if no token is configured.

```bash
make test              # Unit tests only (default)
make integration-test  # Live API tests (requires token)
```

## Architecture

- **`config.py`**: Centralized config/token path management with env var overrides
- **`client.py`**: Auth and generic `_request()` for GraphQL calls
- **Operation modules** (accounts.py, categories.py, transactions/*.py): API calls and formatting
- **`cli.py`**: Thin Click wrapper over operation modules
- **`mcp/server.py`**: MCP server exposing same operations to AI assistants

## Architecture Notes

This project follows a CLI/MCP/SDK layered architecture:
- **SDK layer** (`monarch/*.py`): Business logic, reusable
- **CLI layer** (`monarch/cli.py`): Thin Click wrapper
- **MCP layer** (`monarch/mcp/`): Thin MCP wrapper exposing SDK to AI assistants

## Monarch API Behaviors

Observations from working with the Monarch Money GraphQL API. These are not documented by Monarch — they're discovered through testing. Introspection queries are disabled for non-admin users, so mutation names and input shapes must be reverse-engineered.

### Two Recurring Query Types

Monarch has two separate GraphQL queries for recurring data:

| Query | Returns | Payment status? | Credit report liabilities? |
|-------|---------|-----------------|---------------------------|
| `Web_GetUpcomingRecurringTransactionItems` | Date-specific occurrences (many per stream) | Yes (`isPast`, `transactionId`, `date`, `category`, `account`) | No |
| `Common_GetRecurringStreams` | One entry per stream (catalog) | No | Yes (with `includeLiabilities: true`) |

Everything in the first query is a subset of the second. The second is a superset that also includes inactive/stale streams and credit report liabilities.

### Credit Report Liability Streams

Streams sourced from credit bureau data (not transaction detection). These have:
- `merchant: null` — no merchant association
- `amount: null` — no fixed payment amount (balance varies)
- `recurringType`: `credit_card`, `expense` (mortgages), or `credit_line`
- `creditReportLiabilityAccount` with: `status` (OPEN/CLOSED), `accountType` (MORTGAGE/REVOLVING/CREDIT_LINE/INSTALLMENT), `reportedDate`, and linked `account` with balance

Fields NOT available on credit report liabilities (all return 400): `lastStatementBalance`, `minimumPayment`, `lastPaymentAmount`, `dueDate`, `creditLimit`, `apr`, `monthlyPayment`.

The Monarch UI displays payment amounts and due dates for these streams, but the API doesn't expose how those are derived — likely from account statement data or transaction history.

### Merchant-Level Recurring

Recurring streams are controlled through the **merchant** resource:
- Each merchant has a recurring flag (on/off), amount, and frequency
- Toggling recurring on a merchant creates streams; toggling off removes ALL streams for that merchant
- One merchant can have multiple streams (different detection patterns from varying payee names)
- The `markStreamAsNotRecurring(streamId)` mutation removes a stream but affects all streams for its merchant

### Merchant Data Staleness

When a loan transfers between servicers (e.g., from one mortgage company to another), Monarch's merchant may retain the old loan's amount and recurring settings. The new servicer creates a new merchant with its own detection. The old merchant's data becomes stale but is never automatically cleaned up.

### Duplicate Streams

Monarch creates separate streams when the same payee's transaction description varies (e.g., different abbreviations, location suffixes, or "Memorial" vs regular entries). These are the same real-world obligation but appear as 2-3 separate streams.

### `last_paid_date` Null Behavior

In the collapsed stream output, `last_paid_date: null` means no transaction was matched to any occurrence in the trailing 12-month window. This could mean:
- The stream is genuinely stale (no payments ever or account closed)
- The payment comes from an account not linked to Monarch
- The merchant name changed and payments now post under a different merchant
- The account credential is disconnected and transactions stopped syncing

The null is ambiguous — consumers should investigate rather than assume "never paid."

### Mutation Discovery

Schema introspection is disabled. Known working mutations:
- `markStreamAsNotRecurring(streamId: ID!)` — removes stream (merchant-level effect)
- Requesting `errors { ... }` sub-fields alongside `success` causes HTTP 400. Request only `success`.

Unknown: merchant update mutation for changing recurring amount/frequency/flag programmatically. The UI does this but the mutation name hasn't been captured from DevTools yet.
