import csv
from pathlib import Path

from src.csv_ingestion import process_events
from src.usage_aggregation import aggregate_usage
from src.invoice_engine import generate_invoices, load_commands


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

    with open(events_path, "r", newline="", encoding="utf-8-sig") as file:
        events = list(csv.DictReader(file))

    decisions = {
        row["event_id"]: row
        for row in read_output("event_decisions.csv")
    }

    print(f"\nTHROTTLE LOG: {start_date} to {end_date}")

    count = 0

    for event in events:
        event_date = event["event_ts"][:10]

        if not start_date <= event_date <= end_date:
            continue

        decision = decisions.get(event["event_id"])

        if decision is None:
            continue

        if float(decision["throttled_quantity"]) <= 0:
            continue

        count += 1

        print(
            f"{event['event_id']} | "
            f"{event['customer_id']} | "
            f"{event['event_ts']} | "
            f"throttled={decision['throttled_quantity']} | "
            f"{decision['reason']}"
        )

    print(f"Throttled events: {count}")


def execute_commands():
    commands = load_commands()

    print("=" * 55)
    print("PS-089 API USAGE METERING AND BILLING")
    print("=" * 55)

    # The ingestion module processes OPEN_MONTH and
    # INGEST_UNTIL in their original command-file order.
    print("\n[1/3] Processing usage events...")
    process_events()

    # Generate the complete usage summary.
    print("\n[2/3] Aggregating usage...")
    aggregate_usage()

    # Invoice generation uses the official monthly
    # GENERATE_INVOICES cutoffs from commands.txt.
    print("\n[3/3] Generating invoices...")
    generate_invoices()

    print("\nExecuting report commands...")

    for parts in commands:
        command = parts[0]

        if command == "PRINT_USAGE":
            print_usage(parts[1], parts[2])

        elif command == "PRINT_INVOICE":
            print_invoice(parts[1], parts[2])

        elif command == "PRINT_THROTTLE_LOG":
            print_throttle_log(parts[1], parts[2])

    print("\nAll commands completed.")


if __name__ == "__main__":
    execute_commands()
