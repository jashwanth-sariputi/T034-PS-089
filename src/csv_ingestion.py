
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input" / "T034-Dataset"
OUTPUT = ROOT / "output"

PLAN_QUOTAS = {
    "STARTER": 100_000,
    "GROWTH": 1_000_000,
    "SCALE": 10_000_000,
}

FREE_API_CALLS = Decimal("10000")
RATE_LIMIT = 600
BURST_LIMIT = 100


def parse_timestamp(value):
    """Dataset timestamps are UTC, without timezone suffix."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def format_quantity(value):
    value = Decimal(value)
    return format(value.normalize(), "f")


def load_csv(filename):
    with open(INPUT / filename, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def save_csv(filename, rows, columns):
    OUTPUT.mkdir(exist_ok=True)

    with open(OUTPUT / filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)



def create_ingestion_state():
    customers = {
        row["customer_id"]: row
        for row in load_csv("customers.csv")
    }

    events = load_csv("usage_events.csv")

    return {
        "customers": customers,
        "events": events,
        "first_ingestion": {},
        "free_used": defaultdict(Decimal),
        "quota_used": defaultdict(Decimal),
        "rate_history": defaultdict(list),
        "burst_used": defaultdict(int),
        "decisions": {},
        "event_index": 0,
        "open_month": None,
    }


def open_ingestion_month(state, month):
    if not month:
        raise ValueError("OPEN_MONTH requires a month")

    state["open_month"] = month
    print(f"\nOpened usage month: {month}")


def save_event_decisions(state, require_complete=False):
    events = state["events"]
    decisions = state["decisions"]

    if require_complete and len(decisions) != len(events):
        remaining = len(events) - len(decisions)
        raise ValueError(
            f"{remaining} events were not processed. "
            "Check the final INGEST_UNTIL command."
        )

    output_rows = [
        decisions[event["event_id"]]
        for event in events
        if event["event_id"] in decisions
    ]

    columns = [
        "event_id",
        "decision",
        "metered_quantity",
        "throttled_quantity",
        "blocked_quantity",
        "overage_quantity",
        "reason",
    ]

    save_csv("event_decisions.csv", output_rows, columns)


def ingest_until(state, cutoff_value):
    if state["open_month"] is None:
        raise ValueError(
            "OPEN_MONTH must come before ingestion"
        )

    cutoff = parse_timestamp(cutoff_value)

    events = state["events"]
    event_index = state["event_index"]
    decisions = state["decisions"]

    while event_index < len(events):
        event = events[event_index]

        ingestion_time = parse_timestamp(
            event["ingested_ts"]
        )

        if ingestion_time >= cutoff:
            break

        decision = process_one_event(
            event,
            state["customers"],
            state["first_ingestion"],
            state["free_used"],
            state["quota_used"],
            state["rate_history"],
            state["burst_used"],
        )

        decisions[event["event_id"]] = decision
        event_index += 1

    state["event_index"] = event_index

    save_event_decisions(state)

    print(
        f"Ingested events: {event_index}/{len(events)}"
    )
    print(f"Ingestion cutoff: {cutoff_value}")


def process_events():
    state = create_ingestion_state()

    commands = (INPUT / "commands.txt").read_text(
        encoding="utf-8-sig"
    ).splitlines()

    for line in commands:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split("|")
        command = parts[0]

        if command == "OPEN_MONTH":
            open_ingestion_month(state, parts[1])

        elif command == "INGEST_UNTIL":
            ingest_until(state, parts[1])

    save_event_decisions(
        state,
        require_complete=True,
    )

    print(
        f"Processed events: {state['event_index']}"
    )
    print(
        f"Output: {OUTPUT / 'event_decisions.csv'}"
    )

def process_one_event(
    event,
    customers,
    first_ingestion,
    free_used,
    quota_used,
    rate_history,
    burst_used,
):
    event_id = event["event_id"]
    customer_id = event["customer_id"]
    metric_id = event["metric_id"]
    key = (customer_id,metric_id, event["idempotency_key"])

    event_time = parse_timestamp(event["event_ts"])
    ingestion_time = parse_timestamp(event["ingested_ts"])
    quantity = Decimal(event["quantity"])

    result = {
        "event_id": event_id,
        "decision": "",
        "metered_quantity": "0",
        "throttled_quantity": "0",
        "blocked_quantity": "0",
        "overage_quantity": "0",
        "reason": "",
    }

    def reject(status, reason):
        result["decision"] = status
        result["reason"] = reason
        return result

    if event_time < ingestion_time - timedelta(hours=72):
        return reject("REJECTED_LATE", "Event is more than 72 hours old")

    if event_time > ingestion_time + timedelta(minutes=5):
        return reject("REJECTED_FUTURE", "Event is more than 5 minutes ahead")

    if key in first_ingestion:
        elapsed = ingestion_time - first_ingestion[key]

        if elapsed <= timedelta(hours=24):
            return reject("DUPLICATE", "Idempotency key repeated within 24 hours")

    else:
        first_ingestion[key] = ingestion_time

    customer = customers[customer_id]
    month = event_time.strftime("%Y-%m")
    month_key = (customer_id, month)

    allowed = quantity
    throttled = Decimal("0")

    # API calls: rolling 60-second limit and hourly burst.
    if metric_id == "API_CALLS":
        previous = rate_history[customer_id]

        window_count = sum(
            count
            for timestamp, count in previous
            if event_time - timedelta(seconds=60) < timestamp <= event_time
        )

        normal_remaining = max(0, RATE_LIMIT - window_count)

        hour_key = (
            customer_id,
            event_time.strftime("%Y-%m-%d %H"),
        )

        burst_remaining = max(
            0,
            BURST_LIMIT - burst_used[hour_key],
        )

        allowed = min(
            quantity,
            Decimal(normal_remaining + burst_remaining),
        )

        normal_used = min(allowed, Decimal(normal_remaining))
        burst_used_now = allowed - normal_used

        burst_used[hour_key] += int(burst_used_now)

        throttled = quantity - allowed

        if allowed > 0:
            previous.append((event_time, int(allowed)))

    # Apply free allowance and monthly API quota.
    metered = allowed
    overage = Decimal("0")
    blocked = Decimal("0")

    if metric_id == "API_CALLS":
        free_remaining = max(
            Decimal("0"),
            FREE_API_CALLS - free_used[month_key],
        )

        free_quantity = min(allowed, free_remaining)
        free_used[month_key] += free_quantity

        after_free = allowed - free_quantity

        quota = Decimal(PLAN_QUOTAS[customer["plan_id"]])

        quota_remaining = max(
            Decimal("0"),
            quota - quota_used[month_key],
        )

        within_quota = min(after_free, quota_remaining)
        beyond_quota = after_free - within_quota

        overage_enabled = customer["overage_enabled"].lower() == "true"

        if overage_enabled:
            overage = beyond_quota
            quota_used[month_key] += after_free
        else:
            blocked = beyond_quota
            quota_used[month_key] += within_quota

        metered = free_quantity + within_quota

    result["metered_quantity"] = format_quantity(metered)
    result["throttled_quantity"] = format_quantity(throttled)
    result["blocked_quantity"] = format_quantity(blocked)
    result["overage_quantity"] = format_quantity(overage)

    if blocked > 0 or throttled > 0:
        result["decision"] = "PARTIAL" if metered + overage > 0 else (
            "THROTTLED" if throttled > 0 else "BLOCKED"
        )
    elif overage > 0:
        result["decision"] = "OVERAGE"
    else:
        result["decision"] = "METERED"

    reasons = []

    if throttled > 0:
        reasons.append("Rate limit exceeded")

    if blocked > 0:
        reasons.append("Monthly quota exceeded; overage disabled")

    if overage > 0:
        reasons.append("Usage beyond monthly quota")

    result["reason"] = "; ".join(reasons)

    return result


if __name__ == "__main__":
    process_events()
