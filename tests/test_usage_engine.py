from decimal import Decimal

from src.csv_ingestion import parse_timestamp, format_quantity
from src.usage_aggregation import round_up


def test_parse_timestamp():
    result = parse_timestamp("2026-09-01 00:00:00")

    assert result.year == 2026
    assert result.month == 9
    assert result.day == 1


def test_format_quantity():
    assert format_quantity(Decimal("589.000")) == "589"
    assert format_quantity(Decimal("0.5000")) == "0.5"


def test_round_up_storage():
    result = round_up(
        Decimal("151.3455"),
        Decimal("0.01")
    )

    assert result == Decimal("151.35")


def test_round_up_api_calls():
    result = round_up(
        Decimal("10000.2"),
        Decimal("1")
    )

    assert result == Decimal("10001")


def test_round_up_zero():
    assert round_up(
        Decimal("0"),
        Decimal("1")
    ) == Decimal("0")


def test_round_up_negative():
    assert round_up(
        Decimal("-5"),
        Decimal("1")
    ) == Decimal("0")