"""Common transaction formatting utilities."""


def fmt_money(amount: float) -> str:
    """Format amount as currency string."""
    if amount is None:
        return "$0.00"
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"
