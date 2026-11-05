
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input" / "T034-Dataset"
OUTPUT = ROOT / "output"
CONFIG = ROOT / "config"


METRIC_MAPPING = {
    "API_CALLS": "API_CALLS",
    "STORAGE_GB": "STORAGE",
    "ACTIVE_USERS": "ACTIVE_USERS",
}


def load_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def save_csv(filename, rows, columns):
    OUTPUT.mkdir(exist_ok=True)

    with open(OUTPUT / filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_metrics():
    with open(CONFIG / "metrics.json", encoding="utf-8") as file:
        config = json.load(file)

    return {
        item["metric_code"]: item
        for item in config["metrics"]
    }


def round_up(value, unit):
    if value <= 0:
        return Decimal("0")

    return (
        (value / unit).to_integral_value(rounding=ROUND_CEILING)
        * unit
    )


def aggregate_usage():
    events = load_csv(INPUT / "usage_events.csv")

    decisions = {
        row["event_id"]: row
        for row in load_csv(OUTPUT / "event_decisions.csv")
    }

    metrics = load_metrics()
    grouped = defaultdict(list)

    for event in events:
        decision = decisions[event["event_id"]]

        if decision["decision"] in {
            "DUPLICATE",
            "REJECTED_LATE",
            "REJECTED_FUTURE",
        }:
            continue

        metric_code = METRIC_MAPPING[event["metric_id"]]

        grouped[
            (
                event["customer_id"],
                event["event_ts"][:7],
                metric_code,
            )
        ].append((event, decision))

    results = []

    for (customer_id, month, metric_code), records in sorted(grouped.items()):

        metric = metrics[metric_code]
        aggregation = metric["aggregation_type"]

        precision = int(metric["rounding_precision"])
        rounding_unit = Decimal("1").scaleb(-precision)

        # API calls: SUM
        if aggregation == "SUM":

            raw_quantity = sum(
                (
                    Decimal(decision["metered_quantity"])
                    + Decimal(decision["overage_quantity"])
                    for _, decision in records
                ),
                Decimal("0"),
            )

        # Active users: UNIQUE
        elif aggregation == "UNIQUE":

            raw_quantity = Decimal(
                len({
                    event["user_id"]
                    for event, decision in records
                    if event["user_id"].strip()
                    and Decimal(decision["metered_quantity"]) > 0
                })
            )

        # Storage: MAX hourly sample, then monthly average
        # Missing hours carry forward the last known value.
        elif aggregation == "MAX_AVG":

            hourly_samples = {}

            for event, decision in records:

                quantity = Decimal(decision["metered_quantity"])

                if quantity <= 0:
                    continue

                hour = datetime.strptime(
                    event["event_ts"],
                    "%Y-%m-%d %H:%M:%S"
                ).replace(minute=0, second=0)

                hourly_samples[hour] = max(
                    hourly_samples.get(hour, Decimal("0")),
                    quantity,
                )

            month_start = datetime.strptime(
                month + "-01",
                "%Y-%m-%d"
            )

            next_month = (
                month_start.replace(day=28) + timedelta(days=4)
            ).replace(day=1)

            current_hour = month_start
            last_value = None
            hourly_total = Decimal("0")
            hour_count = 0

            while current_hour < next_month:

                if current_hour in hourly_samples:
                    last_value = hourly_samples[current_hour]

                if last_value is not None:
                    hourly_total += last_value
                    hour_count += 1

                current_hour += timedelta(hours=1)

            raw_quantity = (
                hourly_total / Decimal(hour_count)
                if hour_count else Decimal("0")
            )

        else:
            raise ValueError(
                f"Unsupported aggregation: {aggregation}"
            )

        # Apply metric rounding
        rounded_quantity = round_up(
            raw_quantity,
            rounding_unit
        )

        # Apply free allowance
        free_allowance = Decimal(
            str(metric["free_allowance"])
        )

        free_quantity = min(
            rounded_quantity,
            free_allowance
        )

        billable_quantity = max(
            Decimal("0"),
            rounded_quantity - free_quantity
        )

        results.append({
            "customer_id": customer_id,
            "month": month,
            "metric_id": (
                "STORAGE_GB"
                if metric_code == "STORAGE"
                else metric_code
            ),
            "raw_quantity": str(
                raw_quantity.quantize(Decimal("0.0001"))
            ),
            "rounded_quantity": str(rounded_quantity),
            "free_quantity": str(free_quantity),
            "billable_quantity": str(billable_quantity),
            "overage_quantity": str(
                sum(
                   (
                      Decimal(decision["overage_quantity"])
                      for _, decision in records
                    ),
                    Decimal("0"),
                   )
               ),
        })

    columns = [
        "customer_id",
        "month",
        "metric_id",
        "raw_quantity",
        "rounded_quantity",
        "free_quantity",
        "billable_quantity",
        "overage_quantity",
    ]

    save_csv(
        "usage_summary.csv",
        results,
        columns
    )

    print(f"Usage summaries generated: {len(results)}")
    print(f"Output: {OUTPUT / 'usage_summary.csv'}")


if __name__ == "__main__":
    aggregate_usage()
