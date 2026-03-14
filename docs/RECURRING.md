# Monarch Money Recurring Feature: Analysis & API Research

## Goal

Evaluate Monarch Money's Recurring feature as a data source for tracking monthly
financial obligations (bills, subscriptions, loan payments, credit card payments)
via API, to power MCP server tools that list and monitor commitments.

---

## How the Recurring Feature Works

Monarch's **Recurring** section tracks bills and subscriptions. It has two modes:

- **Auto-detection**: Scans transaction history for recurring patterns (same merchant,
  regular frequency). New detections are presented for user review — they don't appear
  on the confirmed list without approval.
- **Manual addition**: Users can search for a merchant and add it as recurring through
  the Monarch web/mobile UI.

Once confirmed, a recurring item appears in a calendar/list view:
- **Upcoming** items (not yet paid this period)
- **Completed** items (matched to a transaction)
- Color coding: green = paid as expected, yellow = different amount

Items do **NOT auto-remove**. They persist until the user explicitly marks them as
"not recurring." Monarch also supports an **Active/Canceled** status — canceled items
remain visible but are separated.

### Bill Sync (Liability Accounts)

Monarch has a **Bill Sync** feature via Spinwheel (credit report connection) that pulls
due dates and balances for credit cards and loans. This is separate from the recurring
feature and only covers credit-report-visible liabilities, not utilities or subscriptions.

---

## Data Model

### Streams vs. Items

Monarch uses two levels:

- **Stream** (`recurringTransactionStream`): The recurring obligation itself — one per
  commitment. This is the stable entity that represents "I pay Netflix monthly."
- **Item** (`recurringTransactionItem`): A projected occurrence of a stream for a
  specific date. The API returns items within a date range, and each item may or may
  not be matched to an actual transaction.

The API does not expose a direct "list all streams" endpoint that we've been able to
use. Instead, you query for items within a date range, and each item references its
parent stream. Our implementation queries the current month and deduplicates by stream
ID to produce the stable obligations list.

### Stream Fields

| Field | Description |
|-------|-------------|
| `id` | Unique stream identifier |
| `frequency` | How often it recurs (monthly, weekly, etc.) |
| `amount` | Expected payment amount |
| `isApproximate` | Whether the amount varies |
| `merchant` | Associated merchant (id, name, logoUrl) |

### Item Fields (per occurrence)

| Field | Description |
|-------|-------------|
| `date` | Expected payment date for this occurrence |
| `isPast` | Whether the date has passed |
| `transactionId` | Linked actual transaction ID (null if unpaid) |
| `amount` | Actual or expected amount for this occurrence |
| `amountDiff` | Difference from expected amount |
| `category` | Category (id, name) |
| `account` | Payment account (id, displayName, logoUrl) |

---

## Key Constraint: Transaction-Seeded

You **cannot create a recurring item from scratch** independent of a transaction.
Recurring items emerge from transaction patterns — either auto-detected or triggered
by manual merchant search that matches existing transactions. There is no freeform
"add an arbitrary obligation" capability.

**Workaround**: Create a manual transaction in Monarch for the merchant, then confirm
it as recurring. Once it's on the list, it persists regardless of future transaction
activity.

---

## Category Limitations

Monarch categories are **system-defined and not customizable**. You cannot create
custom categories like "Monthly Obligations" or "Critical Bills."

This creates a specific problem for credit card payments: they're categorized as
**"Transfer"** — the same category used for moving money between accounts, paying
yourself back, etc. There's no way to distinguish "credit card payment (obligation)"
from "savings transfer (not an obligation)" by category alone.

Monarch does support **tags** (user-created, freeform) on transactions. Whether tags
are available on recurring streams is unconfirmed and would need to be verified in the
web app.

### Available Filter/Grouping Dimensions

Data available on each recurring item that could be used for client-side filtering:

| Field | Example Values | Useful For |
|-------|---------------|------------|
| Category | Mortgage, Entertainment, Transfer | Grouping by type (imprecise for CC payments) |
| Account | Checking, Credit Card, Loan | Grouping by payment source |
| Frequency | monthly, weekly, biweekly | Filtering to just monthly |
| Merchant | Netflix, Chase, MOHELA | Matching specific obligations |
| Amount | -15.49, -2500.00 | Sorting by size |
| isApproximate | true/false | Fixed vs. variable amounts |
| Payment status | paid/unpaid | Show only outstanding |

The API accepts a `$filters: RecurringTransactionFilter` parameter, but the schema
for this filter type is **undocumented**. The fields it accepts would need to be
reverse-engineered from the Monarch web app's network traffic.

---

## Available GraphQL API Operations

### Queries (Read)

| Operation Name | Purpose | Implemented |
|---------------|---------|-------------|
| `Web_GetUpcomingRecurringTransactionItems` | Items for a date range with stream, merchant, account, category | **Yes** |
| `Common_GetRecurringStreams` | Raw stream definitions (no date range) | No |
| `Common_GetAggregatedRecurringItems` | Aggregated view with status grouping | No |
| `Web_GetAllRecurringTransactionItems` | All items with filtering | No |
| `GetBills` | Bills and payments with due dates | No |
| `RecurringMerchantSearch` | Check recurring merchant search status | No |

### Mutations (Write)

| Operation Name | Purpose | Implemented |
|---------------|---------|-------------|
| `Web_ReviewStream` | Review/update a recurring stream | No |
| `Common_MarkAsNotRecurring` | Mark merchant as not recurring | No |

**No create or delete mutations** have been found in any community library.

### Implemented Query

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

### Community Libraries

| Library | Recurring Support |
|---------|-------------------|
| [hammem/monarchmoney](https://github.com/hammem/monarchmoney) (Python) | `get_recurring_transactions()` — read only |
| [keithah/monarchmoney-enhanced](https://github.com/keithah/monarchmoney-enhanced) (Python) | Documents additional query names in GRAPHQL.md |
| [keithah/monarchmoney-ts](https://github.com/keithah/monarchmoney-ts) (TypeScript) | No recurring support |

---

## Our Implementation

### What We Built

The recurring feature is implemented across all layers of this project:

- **GraphQL query**: `RECURRING_TRANSACTION_ITEMS_QUERY` in `monarch/queries.py`
- **Provider layer**: `RecurringProvider` protocol + API and Local implementations
- **SDK module**: `monarch/recurring.py` — raw item fetching, stream collapsing, formatting
- **CLI**: `monarch recurring [--format text|json|csv]`
- **MCP tool**: `list_recurring` — returns deduplicated obligations list

### How It Works

1. Query Monarch API for current month's recurring transaction items
2. `collapse_to_streams()` deduplicates by stream ID → one entry per obligation
3. Each entry includes current-month payment status (`this_month_paid`)
4. Output sorted alphabetically by merchant

The date range is an API implementation detail, not a user-facing concern. The user
runs `monarch recurring` and gets their stable list of obligations with payment status.

### Collapsed Stream Output Fields

| Field | Description |
|-------|-------------|
| `stream_id` | Unique stream identifier |
| `merchant` | Merchant/payee name |
| `merchant_id` | Merchant ID |
| `amount` | Expected monthly amount |
| `frequency` | Recurrence frequency |
| `is_approximate` | Whether amount varies |
| `category` | Monarch category name (inherited from transaction) |
| `category_id` | Category ID |
| `account` | Payment account name |
| `account_id` | Account ID |
| `is_past` | Whether the due date has passed (Monarch's raw `isPast`) |
| `due_date` | Expected payment date for the current month (YYYY-MM-DD) |
| `last_paid_date` | Date of most recent paid occurrence in trailing 12 months (YYYY-MM-DD, null if never paid) |
| `actual_amount` | Actual or expected amount this month |
| `transaction_id` | Matched transaction ID for current month (null if unpaid) |

### Payment Status

The MCP tool and JSON output return Monarch's raw fields (`is_past`, `transaction_id`)
directly. No derived status field — the consumer interprets them:

| `is_past` | `transaction_id` | Meaning |
|-----------|-----------------|---------|
| false | null | Not due yet this month |
| true | non-null | Paid — payment matched to a transaction |
| true | null | Due date passed, no matching payment found |

The text display derives a human-readable label (PAID/OVERDUE/UPCOMING) from these
two fields for convenience, but the MCP tool surfaces the raw data so consumers can
use or ignore the payment status as they see fit. The primary list value is the
obligations themselves — the payment status is supplementary enrichment.

Additionally, `last_paid_date` provides the date of the most recent paid occurrence
across the trailing 12 months. This is independent of the current month — comparing
`last_paid_date` to `due_date` gives a clear picture of whether a payment is current
regardless of where you are in the billing cycle. A `last_paid_date` of null means
no payment was matched in the past year.

---

## Architecture Considerations for Obligations Tracking

### The Core Problem

Monarch's recurring list is useful but has stability concerns as a sole source of truth:

- Items are transaction-seeded, not user-declared
- Merchant names can change upstream
- Account disconnections could affect linked items
- Credit card payments are categorized as "Transfer" (indistinguishable from non-obligation transfers)
- No custom categories to tag obligations vs. non-obligations
- `RecurringTransactionFilter` schema is unknown, limiting server-side filtering

### Recommended Approach: Blacklist + Snapshot

Rather than maintaining a separate whitelist of obligations (double maintenance),
use Monarch's recurring list as the source with two guardrails:

1. **Blacklist** (local config): Streams/categories/merchants to ignore. Anything
   in Monarch's recurring that's NOT on the blacklist = your obligations. Less
   maintenance than a whitelist — you only track exceptions.

2. **Snapshot comparison**: Cache the previous run's list and alert if anything
   disappeared between runs. Catches silent removal (merchant changes, account
   disconnects, etc.) without requiring a full whitelist.

### Alternative: Whitelist (Local Config as Source of Truth)

For maximum control, maintain a YAML/JSON config file as the canonical register:

```yaml
obligations:
  - name: Mortgage
    amount: 2150.00
    monarch_merchant: "ABC Mortgage Co"
    type: loan
  - name: Netflix
    amount: 15.49
    monarch_merchant: "Netflix"
    type: subscription
  - name: Chase Sapphire
    amount: null
    monarch_merchant: "Chase Credit Card"
    type: credit_card
```

Monarch becomes enrichment only. Higher maintenance but absolute control.

### Enrichment Queries (Available Now)

For either approach, these queries provide additional context per obligation:

| Query | Enrichment |
|-------|-----------|
| `GetAccounts` | Current balances for credit cards and loan accounts |
| `GetTransactionsList` (filter by merchant) | Last paid date, payment history |
| `GetBills` (not yet implemented) | Due dates and statement balances via Bill Sync |

---

## Open Questions / Future Work

1. **`RecurringTransactionFilter` schema**: What fields does this filter accept?
   Capture from Monarch web app DevTools (Network tab → filter graphql requests).

2. **`Common_GetRecurringStreams` query**: Would return streams directly without
   needing to query items and deduplicate. Schema needs to be captured from web app
   or the `monarchmoney-enhanced` fork.

3. **Tags on recurring streams**: Can tags be applied to recurring items? If yes,
   this could replace the blacklist approach — tag items as "track" or "ignore."

4. **Create recurring mutation**: Reverse-engineer from web app by capturing the
   network request when adding a recurring merchant through the UI.

5. **Client-side filtering**: Add filter parameters to CLI/MCP tool (by category,
   account, frequency, paid status, merchant search).

---

## Q&A: Analysis Discussion Log

Key questions and answers from the research and design process.

### Can I store my obligations list in Monarch?

**Yes, but with caveats.** You can add recurring items through the Monarch UI (manually
search for a merchant and add it). Once added, items persist until you explicitly remove
them. However, recurring items are **transaction-seeded** — you can't create one from
thin air without at least one matching transaction. If you need to add a brand-new
obligation with no history, you'd first create a manual transaction in Monarch to seed it.

### Can the API create new recurring items?

**No known mutation exists.** No community library (Python, TypeScript, Go) has found
a `CreateRecurringStream` or equivalent mutation. The mutations that do exist are
`Web_ReviewStream` (update status) and `Common_MarkAsNotRecurring` (remove). However,
the mutation almost certainly exists internally — it could be captured from the Monarch
web app's network traffic (DevTools → Network → filter `graphql` → add a recurring
merchant and observe the request).

### What about auto-detected items appearing without my control?

Auto-detected items go through a **review flow** — they're presented as suggestions
that you confirm or dismiss. They don't appear on the confirmed list without your
approval. However, the review queue itself could be noisy.

### If I maintain a local whitelist, why use Monarch at all?

You wouldn't need Monarch as the list source — a local config file is more reliable
for stability. But a **blacklist** approach is more practical: let Monarch be the
source, maintain a local blacklist of things to ignore, and use snapshot comparison
to catch anything that silently drops off.

### What does "stream" mean?

It's Monarch's internal term for a recurring obligation — not data streaming or
financial streaming. A "stream" is a single commitment (e.g., "Netflix, $15.49/month").
It generates "items" which are individual monthly occurrences. Our implementation
collapses items back to streams so the user sees the stable obligations list.

### What would a credit card payment be in the category field?

Most likely **"Transfer"** — the same category Monarch uses for any money movement
between accounts. This is problematic because it makes CC payments (obligations)
indistinguishable from savings transfers or reimbursements (not obligations) by
category alone.

### Is the category on a recurring stream separate from the transaction category?

**No, they're the same.** The recurring stream inherits its category from the
transaction that seeded it. There is no independent "stream category" field. If the
source transaction is categorized as "Transfer", the stream's category will be
"Transfer". Recategorizing the source transaction would change the stream's category.

### Can I create custom categories?

**No.** Monarch categories are system-defined. You cannot add custom categories like
"Monthly Obligations" or "Critical Bills." Tags (user-created, freeform) exist on
transactions, but it's unconfirmed whether they're available on recurring streams.

### What are the date range parameters for?

The Monarch API requires a date range to return recurring items — but these are
**projected occurrences**, not actual transactions. If you query January–March, you
get 3 rows per stream (one per month). The date range determines which projected
occurrences you see, not which obligations exist. For the stable obligations list,
the date range is an implementation detail — our CLI/MCP tool handles it internally
(current month) and doesn't expose it to the user.

### How reliable is the payment status?

The status relies on Monarch's ability to match a transaction to a recurring stream.
This works well when the merchant name and amount match closely. Potential issues:

- **Variable amounts** (e.g., credit card minimum payments): If the payment amount
  differs significantly from the expected amount, Monarch may not match it. The
  `isApproximate` flag on the stream indicates variable amounts.
- **Late-month due dates**: A bill due the 28th will correctly show "upcoming" on
  the 5th. This is accurate — it hasn't been paid yet. Once paid, it flips to "paid."
  The status reflects reality for the current month.
- **Payment timing across month boundaries**: If you pay a bill on March 30 for an
  April 1 due date, the March query would show it as "paid" for March. The April
  query would show April's occurrence as "upcoming" until matched.

The `overdue` status is the most actionable signal — it means the due date has passed
and no matching transaction was found. This is the clear indicator for "I need to
check on this."

### What if something silently disappears from the list?

This is the core stability concern. Monarch's recurring list could lose items if:
- A merchant name changes upstream
- An account gets disconnected
- Monarch changes its retention/detection behavior

The **blacklist + snapshot** approach mitigates this: cache the previous list and
diff against the current one. If a stream disappears that isn't on your blacklist,
flag it. This hasn't been implemented yet (see Open Questions).

### How can I filter or categorize streams?

**Server-side**: The API accepts `$filters: RecurringTransactionFilter` but the
schema is undocumented. Fields would need to be reverse-engineered.

**Client-side** (using data we already return): Category, account, frequency,
merchant name, amount, isApproximate, and payment status are all available for
filtering. We don't currently expose filter parameters on the CLI or MCP tool.

---

## Sources

- [Tracking Recurring Expenses and Bills — Monarch Help](https://help.monarch.com/hc/en-us/articles/4890751141908-Tracking-Recurring-Expenses-and-Bills)
- [Track Recurring Bills and Subscriptions — Monarch Blog](https://www.monarch.com/blog/track-recurring-bills-and-subscriptions)
- [Recurring Feature Page — Monarch](https://www.monarchmoney.com/features/recurring)
- [Getting Started with Bill Sync — Monarch Help](https://help.monarch.com/hc/en-us/articles/29446697869076-Getting-Started-with-Bill-Sync)
- [monarchmoney Python Library — GitHub](https://github.com/hammem/monarchmoney)
- [monarchmoney-enhanced Fork — GitHub](https://github.com/keithah/monarchmoney-enhanced)
- [monarchmoney TypeScript SDK — GitHub](https://github.com/keithah/monarchmoney-ts)
