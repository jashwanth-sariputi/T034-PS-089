
from decimal import Decimal

from src.invoice_engine import (
    calculate_commitment,
    calculate_rollover_usage,
    calculate_sla_percentage,
    calculate_sla_credit,
    calculate_gst,
)


def test_commitment_without_commitment():
    customer = {"monthly_commitment": "0"}

    result = calculate_commitment(
        customer,
        Decimal("1000"),
    )

    assert result["commitment_discount"] == Decimal("0")
    assert result["commitment_topup"] == Decimal("0")
    assert result["base_charge"] == Decimal("1000.00")
    assert result["rollover_created"] == Decimal("0")


def test_commitment_discount():
    customer = {"monthly_commitment": "500"}

    result = calculate_commitment(
        customer,
        Decimal("1000"),
    )

    assert result["commitment_discount"] == Decimal("150.00")
    assert result["commitment_topup"] == Decimal("0.00")
    assert result["base_charge"] == Decimal("850.00")


def test_commitment_topup_and_rollover():
    customer = {"monthly_commitment": "1000"}

    result = calculate_commitment(
        customer,
        Decimal("1000"),
    )

    assert result["commitment_discount"] == Decimal("150.00")
    assert result["commitment_topup"] == Decimal("150.00")
    assert result["base_charge"] == Decimal("1000.00")
    assert result["rollover_created"] == Decimal("150.00")


def test_rollover_fully_used():
    result = calculate_rollover_usage(
        Decimal("200"),
        Decimal("150"),
    )

    assert result["rollover_used"] == Decimal("150.00")
    assert result["adjusted_overage"] == Decimal("0.00")


def test_rollover_partially_used():
    result = calculate_rollover_usage(
        Decimal("100"),
        Decimal("250"),
    )

    assert result["rollover_used"] == Decimal("100.00")
    assert result["adjusted_overage"] == Decimal("150.00")


def test_sla_percentage_below_95():
    assert calculate_sla_percentage(
        Decimal("94.500")
    ) == Decimal("50")


def test_sla_percentage_below_99_9():
    assert calculate_sla_percentage(
        Decimal("99.899")
    ) == Decimal("10")


def test_sla_percentage_at_99_9():
    assert calculate_sla_percentage(
        Decimal("99.900")
    ) == Decimal("0")


def test_sla_credit_is_capped():
    uptime_records = {
        ("API-001", "2026-09"): Decimal("94.500")
    }

    result = calculate_sla_credit(
        "API-001",
        "2026-09",
        Decimal("1000"),
        Decimal("200"),
        uptime_records,
    )

    assert result == Decimal("200.00")


def test_karnataka_gst():
    customer = {"state": "Karnataka"}

    result = calculate_gst(
        customer,
        Decimal("1000"),
    )

    assert result["gst"] == Decimal("180.00")
    assert result["cgst"] == Decimal("90.00")
    assert result["sgst"] == Decimal("90.00")
    assert result["igst"] == Decimal("0")


def test_other_state_gst():
    customer = {"state": "Maharashtra"}

    result = calculate_gst(
        customer,
        Decimal("1000"),
    )

    assert result["gst"] == Decimal("180.00")
    assert result["cgst"] == Decimal("0")
    assert result["sgst"] == Decimal("0")
    assert result["igst"] == Decimal("180.00")
