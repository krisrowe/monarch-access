# Research: Monarch Money Recurring Feature as Monthly Obligations Register

## Goal

Determine whether Monarch Money's Recurring feature (or another feature) can serve as
a reliable, user-controlled, independent register of monthly financial obligations
(bills, subscriptions, loan payments, credit card payments) that can be queried via
API to build an MCP server tool that lists monthly commitments.

## Key Requirements

1. **Independent of transaction history** - obligations persist even with no matching transactions
2. **Explicit user control** - items don't auto-remove; user decides what stays on the list
3. **Covers all commitment types** - services/subscriptions, loan payments, credit card payments
4. **API-queryable** - can be retrieved programmatically to power an MCP tool

---

## Findings: Monarch Recurring Feature

### How It Works

Monarch's **Recurring** section is designed to track bills and subscriptions. It operates
in two modes:

- **Auto-detection**: Scans transaction history and identifies recurring patterns
  (same merchant, regular frequency). Presents these as candidates for review.
- **Manual addition**: Users can manually search for and add a recurring merchant,
  even without existing transactions.

Once a recurring item exists, it appears on a calendar/list view with:
- **Upcoming** items (not yet paid this period)
- **Completed** items (matched to a transaction this period)
- Color coding: green = paid as expected, yellow = paid at different amount

### Data Model: Recurring Streams

The core data entity is a **recurring stream** (`recurringTransactionStream`), which
represents a recurring obligation. Each stream has:

| Field | Description |
|-------|-------------|
| `id` | Unique stream identifier |
| `frequency` | How often it recurs (monthly, weekly, etc.) |
| `amount` | Expected payment amount |
| `isApproximate` | Whether the amount varies |
| `merchant` | Associated merchant (id, name, logoUrl) |
| `category` | Assigned category |
| `account` | Associated payment account |

The stream generates **recurring transaction items** for specific dates, each with:
- `date` - expected payment date
- `isPast` - whether the date has passed
- `transactionId` - linked actual transaction (if paid)
- `amount` - actual or expected amount
- `amountDiff` - difference from expected

### User Control

| Capability | Supported? | Details |
|------------|-----------|---------|
| Manually add recurring items | Yes | Search for merchant and add |
| Edit amount, frequency, date | Yes | Via "Edit merchant details" |
| Mark as not recurring (remove) | Yes | Explicit user action required |
| Auto-removal | No | Items persist until user removes them |
| Review flow for new detections | Yes | User must approve auto-detected items |
| Multiple items per merchant | Workaround | Create variant merchant names |

**Key finding**: Items do NOT auto-remove. They persist on the recurring list until the
user explicitly marks them as not recurring. This is the behavior needed for an
independent obligations register.

### Bill Sync (Liability Accounts)

Monarch also has a **Bill Sync** feature that connects to credit reports via Spinwheel
to pull in bill due dates and balances for liability accounts (credit cards, loans).
This provides:
- Due dates from the actual creditor
- Balance information
- Payment status

This only works for credit-report-visible liabilities, not utilities or subscriptions.

---

## Available GraphQL API Operations

### Queries (Read)

| Operation Name | Purpose |
|---------------|---------|
| `Web_GetUpcomingRecurringTransactionItems` | Get recurring items for a date range with merchant, account, category details |
| `Common_GetRecurringStreams` | Get all recurring stream definitions |
| `Common_GetAggregatedRecurringItems` | Aggregated view with status grouping |
| `Web_GetAllRecurringTransactionItems` | All recurring items with filtering |
| `GetBills` | Get upcoming bills and payments with due dates |
| `RecurringMerchantSearch` | Check status of recurring merchant search |

### Mutations (Write)

| Operation Name | Purpose |
|---------------|---------|
| `Web_ReviewStream` | Review/update a recurring stream's status |
| `Common_MarkAsNotRecurring` | Mark a merchant as not recurring |

### Key Query: `Web_GetUpcomingRecurringTransactionItems`

```graphql
query Web_GetUpcomingRecurringTransactionItems(
  $startDate: Date!
  $endDate: Date!
  $filters: RecurringTransactionFilter
) {
  recurringTransactionItems(
    startDate: $startDate
    endDate: $endDate
    filters: $filters
  ) {
    stream {
      id
      frequency
      amount
      isApproximate
      merchant { id name logoUrl }
    }
    date
    isPast
    transactionId
    amount
    amountDiff
    category { id name }
    account { id displayName logoUrl }
  }
}
```

### Python Library Support

The `monarchmoney` Python package (by hammem) exposes:

```python
async def get_recurring_transactions(
    self,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]
```

The `Common_GetRecurringStreams` and `GetBills` queries are documented in the
`keithah/monarchmoney-enhanced` fork's GRAPHQL.md but not yet wrapped as Python methods
in the main library.

---

## Assessment: Suitability as Monthly Obligations Register

### Strengths

1. **User-controlled persistence**: Items stay on the list until explicitly removed.
   No auto-pruning. This is the single most important requirement and it is met.

2. **Manual addition**: Users can add recurring items for merchants that don't yet have
   transaction history. You can preload your obligations.

3. **Covers all three commitment types**:
   - **Services/subscriptions**: Core use case for recurring feature
   - **Loan payments**: Can be added as recurring merchants
   - **Credit card payments**: Can be added as recurring; Bill Sync adds due dates

4. **Rich metadata**: Each stream carries merchant, amount, frequency, category,
   and account - enough to identify and cross-reference obligations.

5. **Payment matching**: Monarch automatically matches transactions to recurring items,
   providing built-in "was this paid?" status via `transactionId` and `isPast`.

6. **API accessible**: The GraphQL queries return structured data suitable for
   programmatic consumption.

### Limitations

1. **No dedicated "create recurring" mutation**: The API doesn't expose a mutation to
   programmatically add new recurring items. Adding must be done through the Monarch UI
   or by reverse-engineering additional mutations. This means the register must be
   maintained in Monarch's UI, not via the MCP server.

2. **One recurring per merchant**: Each merchant can only have one recurring stream.
   Workaround: create variant merchant names ("Student Loan - Federal", "Student Loan - Private").

3. **Stream-level data is sparse**: The `stream` object has id, frequency, amount,
   merchant, and isApproximate. It does NOT include fields like: remaining balance,
   interest rate, payoff date, or loan terms. Those would need to come from other sources
   (account data, Bill Sync, external APIs).

4. **`Common_GetRecurringStreams` not in main Python lib**: The query that returns
   the raw stream definitions (independent of date range) is not yet wrapped in the
   main `monarchmoney` package. Would need to be added to this project's queries.

5. **Auto-detection noise**: Monarch may suggest new recurring items based on
   transaction patterns. These require user review but could create noise if not
   managed. However, these are presented for review - they don't pollute the
   confirmed list.

---

## Recommendation

**Yes, Monarch's Recurring feature is suitable as the primary source of truth for
a monthly obligations register.** It meets the core requirements:

- Independent of transaction presence (items persist without matching transactions)
- User-controlled (explicit add/remove, no auto-pruning of confirmed items)
- Covers all commitment types (subscriptions, loans, credit card payments)
- API-queryable with structured data

### Recommended Architecture for MCP Server

```
┌─────────────────────────────────────────────────┐
│              MCP Server Tools                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  list_monthly_obligations                        │
│    → Query: GetRecurringStreams                   │
│    → Returns: All recurring streams as the       │
│      canonical list of obligations               │
│                                                  │
│  get_obligation_status (per obligation)           │
│    → Query: GetUpcomingRecurringTransactionItems  │
│    → Cross-ref: Account balances, transactions   │
│    → Returns: Payment status, last paid date,    │
│      current balance, projected payoff           │
│                                                  │
│  get_obligations_summary                         │
│    → Aggregates all obligations with status       │
│    → Monthly total, paid/unpaid breakdown        │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Queries to Implement

1. **`Common_GetRecurringStreams`** - The master list of all recurring obligations
   (independent of date range). This is the "register."

2. **`Web_GetUpcomingRecurringTransactionItems`** - For a given month, shows which
   obligations are upcoming vs. completed, with matched transactions.

3. **`GetBills`** - For liability accounts with Bill Sync, provides due dates and
   balance information.

4. **Existing queries** (accounts, transactions) - For cross-referencing:
   - Account balances for credit cards and loans
   - Transaction history for "last paid" lookups
   - Category data for obligation classification

### Workflow

1. **User maintains their obligations in Monarch UI** - Adds all monthly commitments
   as recurring items (subscriptions, loan payments, credit card payments).

2. **MCP server reads the recurring streams** - Treats this as the canonical, user-
   controlled register of monthly obligations.

3. **MCP server enriches with cross-referenced data** - For each obligation, queries
   accounts, transactions, and bills to provide:
   - When it was last paid
   - Current account balance (for loans/credit cards)
   - Whether current month's payment is complete
   - Projected payoff (calculated from balance and payment amount)

---

## Sources

- [Tracking Recurring Expenses and Bills - Monarch Help](https://help.monarch.com/hc/en-us/articles/4890751141908-Tracking-Recurring-Expenses-and-Bills)
- [Track Recurring Bills and Subscriptions - Monarch Blog](https://www.monarch.com/blog/track-recurring-bills-and-subscriptions)
- [Recurring Feature Page - Monarch](https://www.monarchmoney.com/features/recurring)
- [Getting Started with Bill Sync - Monarch Help](https://help.monarch.com/hc/en-us/articles/29446697869076-Getting-Started-with-Bill-Sync)
- [monarchmoney Python Library - GitHub](https://github.com/hammem/monarchmoney)
- [monarchmoney-enhanced Fork - GitHub](https://github.com/keithah/monarchmoney-enhanced)
- [monarchmoney TypeScript SDK - GitHub](https://github.com/keithah/monarchmoney-ts)
