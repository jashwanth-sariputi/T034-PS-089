import csv
from pathlib import Path

from src.csv_ingestion import (
    create_ingestion_state,
    open_ingestion_month,
    ingest_until,
    save_event_decisions,
)
from src.rating_engine import generate_ratings
from src.usage_aggregation import aggregate_usage

from src.invoice_engine import (
    create_invoice_state,
    generate_invoice_month,
    load_commands,
)


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input" / "T034-Dataset"
OUTPUT = ROOT / "output"


def read_output(filename):
    path = OUTPUT / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Required output not found: {path}"
        )

    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def print_usage(customer_id, month):
    rows = read_output("usage_summary.csv")

    matches = [
        row for row in rows
        if row["customer_id"] == customer_id
        and row["month"] == month
    ]

    print(f"\nUSAGE REPORT: {customer_id} | {month}")

    if not matches:
        print("No usage records found.")
        return

    for row in matches:
        print(
            f"{row['metric_id']}: "
            f"raw={row['raw_quantity']}, "
            f"rounded={row['rounded_quantity']}, "
            f"free={row['free_quantity']}, "
            f"billable={row['billable_quantity']}, "
            f"overage={row['overage_quantity']}"
        )


def print_invoice(customer_id, month):
    rows = read_output("invoices.csv")

    matches = [
        row for row in rows
        if row["customer_id"] == customer_id
        and row["month"] == month
    ]

    print(f"\nINVOICE: {customer_id} | {month}")

    if not matches:
        print("Invoice not found.")
        return

    for row in matches:
        for key, value in row.items():
            print(f"{key}: {value}")


def print_throttle_log(start_date, end_date):
    events_path = INPUT / "usage_events.csv"

    with open(
        events_path,
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        events = list(csv.DictReader(file))

    decisions = {
        row["event_id"]: row
        for row in read_output("event_decisions.csv")
    }

    print(f"\nTHROTTLE LOG: {start_date} to {end_date}")

    count = 0

    for event in events:
        event_id = event.get("event_id", "")
        customer_id = event.get("customer_id", "")
        event_ts = event.get("event_ts", "")

        if not event_ts:
            continue

        event_date = event_ts[:10]

        if not start_date <= event_date <= end_date:
            continue

        decision = decisions.get(event_id)

        if decision is None:
            continue

        throttled = float(
            decision.get("throttled_quantity") or 0
        )

        blocked = float(
            decision.get("blocked_quantity") or 0
        )

        if throttled <= 0 and blocked <= 0:
            continue

        decision_type = decision.get("decision", "UNKNOWN")
        reason = decision.get("reason", "Not specified")

        count += 1

        print(
            f"{event_id} | "
            f"{customer_id} | "
            f"{event_ts} | "
            f"decision={decision_type} | "
            f"throttled={throttled} | "
            f"blocked={blocked} | "
            f"{reason}"
        )

    print(f"Throttled events: {count}")

def execute_commands():

    commands = load_commands()

    ingestion_state = create_ingestion_state()
    invoice_state = create_invoice_state()

    usage_aggregated = False

    print("=" * 55)
    print("PS-089 API USAGE METERING AND BILLING")
    print("=" * 55)

    print("\nExecuting commands in commands.txt order...")

    for parts in commands:

        command = parts[0]

        if command == "OPEN_MONTH":

            open_ingestion_month(
                ingestion_state,
                parts[1],
            )

        elif command == "INGEST_UNTIL":

            ingest_until(
                ingestion_state,
                parts[1],
            )

        elif command == "GENERATE_INVOICES":

            generate_invoice_month(
                invoice_state,
                parts[1],
                parts[2],
            )

        elif command == "PRINT_USAGE":

            if not usage_aggregated:
               print("\nAggregating usage...")
               aggregate_usage()

               print("\nGenerating rating breakdown...")
               generate_ratings()

               usage_aggregated = True

            print_usage(
                parts[1],
                parts[2],
            )

        elif command == "PRINT_INVOICE":

            print_invoice(
                parts[1],
                parts[2],
            )

        elif command == "PRINT_THROTTLE_LOG":

            print_throttle_log(
                parts[1],
                parts[2],
            )

        else:

            raise ValueError(
                f"Unknown command: {command}"
            )

    # Ensure every dataset event was processed.
    save_event_decisions(
        ingestion_state,
        require_complete=True,
    )

    print("\nAll commands completed.")


if __name__ == "__main__":
    execute_commands()
