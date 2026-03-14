"""Tests for recurring transaction operations."""

from datetime import date, timedelta


class TestRecurringList:
    """Test listing recurring transaction items."""

    def test_get_recurring_returns_list(self, local_provider):
        """Test that get_recurring_transaction_items returns a list."""
        today = date.today()
        start = today.replace(day=1).isoformat()
        # Use a wide range to capture all test data
        end = (today.replace(day=1) + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        assert isinstance(items, list)
        assert len(items) > 0

    def test_recurring_items_have_expected_fields(self, local_provider):
        """Test that recurring items have the expected structure."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        assert len(items) > 0
        item = items[0]

        assert "stream" in item
        assert "date" in item
        assert "isPast" in item
        assert "amount" in item
        assert "category" in item
        assert "account" in item

    def test_recurring_stream_has_expected_fields(self, local_provider):
        """Test that the stream object has merchant, frequency, amount."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        stream = items[0]["stream"]
        assert "id" in stream
        assert "frequency" in stream
        assert "amount" in stream
        assert "merchant" in stream
        assert "name" in stream["merchant"]

    def test_recurring_date_filter(self, local_provider):
        """Test that date filtering works."""
        # Use a very narrow range that shouldn't match any items
        items = local_provider.get_recurring_transaction_items(
            start_date="2020-01-01",
            end_date="2020-01-02",
        )

        assert isinstance(items, list)
        assert len(items) == 0

    def test_recurring_includes_multiple_streams(self, local_provider):
        """Test that multiple recurring streams are returned."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        # Our seed data has 4 recurring streams, each with 3 months of items
        stream_ids = {item["stream"]["id"] for item in items}
        assert len(stream_ids) >= 2, f"Expected multiple streams, got: {stream_ids}"

    def test_recurring_items_sorted_by_date(self, local_provider):
        """Test that items are sorted by date."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        dates = [item["date"] for item in items]
        assert dates == sorted(dates)

    def test_recurring_payment_status(self, local_provider):
        """Test that items have transactionId (paid) or not."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        # transactionId should be present as a key (may be None for unpaid)
        for item in items:
            assert "transactionId" in item
