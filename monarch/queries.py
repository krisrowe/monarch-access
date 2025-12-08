"""GraphQL queries for Monarch Money API."""

ACCOUNTS_QUERY = """
query GetAccounts {
  accounts {
    id
    displayName
    syncDisabled
    deactivatedAt
    isHidden
    isAsset
    mask
    createdAt
    updatedAt
    displayLastUpdatedAt
    currentBalance
    displayBalance
    includeInNetWorth
    dataProvider
    isManual
    type { name display }
    subtype { name display }
    credential {
      id
      updateRequired
      disconnectedFromDataProviderAt
      institution { id name status }
    }
    institution { id name }
  }
}
"""

TRANSACTIONS_QUERY = """
query GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput) {
  allTransactions(filters: $filters) {
    totalCount
    results(offset: $offset, limit: $limit) {
      id
      amount
      pending
      date
      hideFromReports
      needsReview
      plaidName
      notes
      isRecurring
      reviewStatus
      isSplitTransaction
      account {
        id
        displayName
      }
      merchant {
        id
        name
        transactionsCount
      }
      category {
        id
        name
      }
      tags {
        id
        name
        color
      }
    }
  }
}
"""

TRANSACTION_CATEGORIES_QUERY = """
query GetTransactionCategories {
  categories {
    id
    name
    icon
    order
    group {
      id
      name
      type
    }
  }
}
"""
