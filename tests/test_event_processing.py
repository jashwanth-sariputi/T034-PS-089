
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from src.csv_ingestion import process_one_event, parse_timestamp


def create_test_event(
    event_id="EV-TEST001",
    event_ts="2026-09-01 12:00:00",
    ingested_ts="2026-09-01 12:00:30",
    quantity="100",
):
    return {
        "event_id": event_id,
        "idempotency_key": "TESTKEY001",
        "customer_id": "API-TEST",
        "metric_id": "API_CALLS",
        "event_ts": event_ts,
        "ingested_ts": ingested_ts,
        "quantity": quantity,
        "user_id": "",
    }


def create_state(overage_enabled="false"):
    customers = {
        "API-TEST": {
            "plan_id": "STARTER",
            "overage_enabled": overage_enabled,
        }
    }

    return (
        customers,
        {},
        defaultdict(Decimal),
        defaultdict(Decimal),
        defaultdict(list),
        defaultdict(int),
    )


def process(event, state):
    return process_one_event(event, *state)


def test_reject_late_event():
    event = create_test_event(
        event_ts="2026-09-01 00:00:00",
        ingested_ts="2026-09-04 00:00:01",
    )

    result = process(event, create_state())

    assert result["decision"] == "REJECTED_LATE"
    assert result["metered_quantity"] == "0"


def test_reject_future_event():
    event = create_test_event(
        event_ts="2026-09-01 12:06:00",
        ingested_ts="2026-09-01 12:00:00",
    )

    result = process(event, create_state())

    assert result["decision"] == "REJECTED_FUTURE"


def test_duplicate_event():
    event = create_test_event()

    state = create_state()
    key = (
        event["customer_id"],
        event["metric_id"],
        event["idempotency_key"],
    )

    state[1][key] = (
        parse_timestamp(event["ingested_ts"])
        - timedelta(hours=2)
    )

    result = process(event, state)

    assert result["decision"] == "DUPLICATE"
    assert result["metered_quantity"] == "0"


def test_quota_blocking():
    event = create_test_event(quantity="5")

    state = create_state()

    month_key = ("API-TEST", "2026-09")

    state[2][month_key] = Decimal("10000")
    state[3][month_key] = Decimal("100000")

    result = process(event, state)

    assert result["decision"] == "BLOCKED"
    assert result["blocked_quantity"] == "5"
    assert result["metered_quantity"] == "0"


def test_rate_limit_throttling():
    event = create_test_event(quantity="10")

    state = create_state()

    event_time = parse_timestamp(event["event_ts"])

    state[4]["API-TEST"] = [
        (event_time - timedelta(seconds=30), 600)
    ]

    state[5][("API-TEST", "2026-09-01 12")] = 100

    result = process(event, state)

    assert result["decision"] == "THROTTLED"
    assert result["throttled_quantity"] == "10"
    assert result["metered_quantity"] == "0"


def test_overage_enabled():
    event = create_test_event(quantity="5")

    state = create_state(overage_enabled="true")

    month_key = ("API-TEST", "2026-09")

    state[2][month_key] = Decimal("10000")
    state[3][month_key] = Decimal("100000")

    result = process(event, state)

    assert result["decision"] == "OVERAGE"
    assert result["overage_quantity"] == "5"
