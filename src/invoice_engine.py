
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from pathlib import Path


# --------------------------------------------------
# 1. PATHS AND CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input" / "T034-Dataset"
OUTPUT = ROOT / "output"
CONFIG = ROOT / "config"

CUSTOMERS_FILE = INPUT / "customers.csv"
EVENTS_FILE = INPUT / "usage_events.csv"
UPTIME_FILE = INPUT / "uptime.csv"
COMMANDS_FILE = INPUT / "commands.txt"
DECISIONS_FILE = OUTPUT / "event_decisions.csv"
METRICS_FILE = CONFIG / "metrics.json"
PRICE_BOOKS_FILE = INPUT / "price_books.csv"

INVOICE_COLUMNS = [
    "customer_id",
    "month",
    "usage_charge",
    "commitment_discount",
    "commitment_topup",
    "base_charge",
    "overage_charge",
    "adjustments",
    "sla_credit",
    "net",
    "gst",
    "total_rounded",
    "rollover_created",
    "rollover_used",
]

METRIC_MAPPING = {
    "API_CALLS": "API_CALLS",
    "STORAGE_GB": "STORAGE",
    "ACTIVE_USERS": "ACTIVE_USERS",
}


# --------------------------------------------------
# 2. COMMON CSV AND MONEY HELPERS
# --------------------------------------------------

def load_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def save_csv(path, rows, columns):
    OUTPUT.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def round_up(value, unit):
    if value <= 0:
        return Decimal("0")

    return (
        (value / unit).to_integral_value(
            rounding=ROUND_CEILING
        ) * unit
    )


# --------------------------------------------------
# 3. LOAD CONFIGURATION
# --------------------------------------------------

def load_metrics():
    with open(METRICS_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    return {
        item["metric_code"]: item
        for item in config["metrics"]
    }


def load_commands():
    commands = []

    with open(COMMANDS_FILE, "r", encoding="utf-8-sig") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            commands.append(line.split("|"))

    return commands


def load_invoice_cutoffs():
    cutoffs = {}

    for command in load_commands():
        if command[0] == "GENERATE_INVOICES":
            month = command[1]

            run_ts = datetime.strptime(
                command[2],
                "%Y-%m-%d %H:%M:%S",
            )

            cutoffs[month] = run_ts

    return cutoffs


def load_customers():
    customers = load_csv(CUSTOMERS_FILE)

    return {
        row["customer_id"]: row
        for row in customers
    }


def load_price_books():
    price_books = defaultdict(list)

    for row in load_csv(PRICE_BOOKS_FILE):
        key = (
            row["price_book_id"],
            row["metric_id"],
        )

        price_books[key].append(row)

    for tiers in price_books.values():
        tiers.sort(
            key=lambda tier: int(tier["tier_from"])
        )

    return price_books


def load_uptime():
    uptime_records = {}

    for row in load_csv(UPTIME_FILE):
        uptime_records[
            (row["customer_id"], row["month"])
        ] = Decimal(row["uptime_pct"])

    return uptime_records


# --------------------------------------------------
# 4. LOAD EVENTS AND INGESTION DECISIONS
# --------------------------------------------------


def load_event_records(allow_pending=False, cutoff=None):
    events = load_csv(EVENTS_FILE)
    decisions = load_csv(DECISIONS_FILE)

    decision_map = {
        row["event_id"]: row
        for row in decisions
    }

    records = []

    for event in events:
        event_time = datetime.strptime(
            event["event_ts"],
            "%Y-%m-%d %H:%M:%S",
        )

        ingested_time = datetime.strptime(
            event["ingested_ts"],
            "%Y-%m-%d %H:%M:%S",
        )

        decision = decision_map.get(event["event_id"])

        if decision is None:
            if (
                allow_pending
                and cutoff is not None
                and ingested_time >= cutoff
            ):
                continue

            raise ValueError(
                f"Missing decision for event {event['event_id']}"
            )

        records.append({
            "event": event,
            "decision": decision,
            "event_time": event_time,
            "ingested_time": ingested_time,
        })

    return records

def get_month_records(records, month, cutoff):
    selected = []

    rejected_decisions = {
        "DUPLICATE",
        "REJECTED_LATE",
        "REJECTED_FUTURE",
    }

    for record in records:
        event = record["event"]
        decision = record["decision"]

        if event["event_ts"][:7] != month:
            continue

        if record["ingested_time"] >= cutoff:
            continue

        if decision["decision"] in rejected_decisions:
            continue

        selected.append(record)

    return selected


def get_late_adjustment_records(
    records,
    previous_month,
    previous_cutoff,
    current_cutoff,
):
    selected = []

    rejected_decisions = {
        "DUPLICATE",
        "REJECTED_LATE",
        "REJECTED_FUTURE",
    }

    for record in records:
        event = record["event"]
        decision = record["decision"]

        if event["event_ts"][:7] != previous_month:
            continue

        if record["ingested_time"] < previous_cutoff:
            continue

        if record["ingested_time"] >= current_cutoff:
            continue

        if decision["decision"] in rejected_decisions:
            continue

        selected.append(record)

    return selected


# --------------------------------------------------
# 5. MONTHLY USAGE AGGREGATION
# --------------------------------------------------

def aggregate_invoice_usage(records, month, cutoff, metrics):

    selected = get_month_records(
        records,
        month,
        cutoff,
    )

    grouped = defaultdict(list)

    for record in selected:
        event = record["event"]
        decision = record["decision"]

        metric_code = METRIC_MAPPING[event["metric_id"]]

        grouped[
            (
                event["customer_id"],
                metric_code,
            )
        ].append((event, decision))

    results = []

    for (customer_id, metric_code), metric_records in sorted(
        grouped.items()
    ):

        metric = metrics[metric_code]

        aggregation = metric["aggregation_type"]

        precision = int(metric["rounding_precision"])

        rounding_unit = Decimal("1").scaleb(-precision)

        # API CALLS: SUM
        if aggregation == "SUM":

            raw_quantity = sum(
                (
                    Decimal(decision["metered_quantity"])
                    + Decimal(decision["overage_quantity"])
                    for _, decision in metric_records
                ),
                Decimal("0"),
            )

        # ACTIVE USERS: UNIQUE
        elif aggregation == "UNIQUE":

            unique_users = {
                event["user_id"]
                for event, decision in metric_records
                if event["user_id"].strip()
                and Decimal(decision["metered_quantity"]) > 0
            }

            raw_quantity = Decimal(len(unique_users))

        # STORAGE: MAX_AVG
        elif aggregation == "MAX_AVG":

            hourly_samples = {}

            for event, decision in metric_records:

                quantity = Decimal(
                    decision["metered_quantity"]
                )

                if quantity <= 0:
                    continue

                hour = datetime.strptime(
                    event["event_ts"],
                    "%Y-%m-%d %H:%M:%S",
                ).replace(
                    minute=0,
                    second=0,
                )

                hourly_samples[hour] = max(
                    hourly_samples.get(
                        hour,
                        Decimal("0"),
                    ),
                    quantity,
                )

            month_start = datetime.strptime(
                month + "-01",
                "%Y-%m-%d",
            )

            next_month = (
                month_start.replace(day=28)
                + timedelta(days=4)
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
                if hour_count
                else Decimal("0")
            )

        else:
            raise ValueError(
                f"Unsupported aggregation: {aggregation}"
            )

        rounded_quantity = round_up(
            raw_quantity,
            rounding_unit,
        )

        free_allowance = Decimal(
            str(metric["free_allowance"])
        )

        free_quantity = min(
            rounded_quantity,
            free_allowance,
        )

        billable_quantity = max(
            Decimal("0"),
            rounded_quantity - free_quantity,
        )

        overage_quantity = sum(
            (
                Decimal(decision["overage_quantity"])
                for _, decision in metric_records
            ),
            Decimal("0"),
        )

        results.append({
            "customer_id": customer_id,
            "month": month,

            "metric_id": (
                "STORAGE_GB"
                if metric_code == "STORAGE"
                else metric_code
            ),

            "raw_quantity": raw_quantity,
            "rounded_quantity": rounded_quantity,
            "free_quantity": free_quantity,
            "billable_quantity": billable_quantity,
            "overage_quantity": overage_quantity,
        })

    return results


# --------------------------------------------------
# 6. PRICING ENGINE
# --------------------------------------------------

def calculate_metric_charge(usage, tiers):

    billable = usage["billable_quantity"]
    overage = usage["overage_quantity"]

    if billable <= 0:
        return Decimal("0"), Decimal("0")

    regular_quantity = billable - overage

    tier_type = tiers[0]["tier_type"]

    regular_charge = Decimal("0")
    overage_charge = Decimal("0")

    # VOLUME PRICING
    if tier_type == "VOLUME":

        tier = next(
            (
                item for item in tiers
                if billable >= Decimal(item["tier_from"])
                and (
                    not item["tier_to"]
                    or billable <= Decimal(item["tier_to"])
                )
            ),
            None,
        )

        if tier is None:
            raise ValueError(
                f"No volume tier for {usage['customer_id']} "
                f"{usage['metric_id']}"
            )

        unit_price = Decimal(tier["unit_price"])

        multiplier = Decimal(
            tier["overage_multiplier"] or "1"
        )

        regular_charge = (
            regular_quantity * unit_price
        )

        overage_charge = (
            overage * unit_price * multiplier
        )

    # GRADUATED PRICING
    elif tier_type == "GRADUATED":

        for tier in tiers:

            lower = Decimal(tier["tier_from"])

            upper = (
                Decimal(tier["tier_to"])
                if tier["tier_to"]
                else None
            )

            if upper is None:
                quantity = max(
                    Decimal("0"),
                    regular_quantity - lower + Decimal("1"),
                )

            else:
                quantity = max(
                    Decimal("0"),
                    min(regular_quantity, upper)
                    - lower
                    + (
                        Decimal("1")
                        if lower > 0
                        else Decimal("0")
                    ),
                )

            regular_charge += (
                quantity * Decimal(tier["unit_price"])
            )

        if overage > 0:

            top_tier = tiers[-1]

            overage_charge = (
                overage
                * Decimal(top_tier["unit_price"])
                * Decimal(top_tier["overage_multiplier"] or "1")
            )

    # FLAT PRICING
    elif tier_type == "FLAT":

        regular_charge = (
            billable * Decimal(tiers[0]["unit_price"])
        )

    else:
        raise ValueError(
            f"Unsupported tier type: {tier_type}"
        )

    return money(regular_charge), money(overage_charge)


def calculate_usage_charges(
    usage_rows,
    customers,
    price_books,
):
    charges = defaultdict(
        lambda: {
            "usage_charge": Decimal("0"),
            "overage_charge": Decimal("0"),
        }
    )

    for usage in usage_rows:

        customer = customers[usage["customer_id"]]

        tiers = price_books.get(
            (
                customer["price_book_id"],
                usage["metric_id"],
            )
        )

        if not tiers:
            raise ValueError(
                f"Missing pricing for {usage['metric_id']} "
                f"and price book {customer['price_book_id']}"
            )

        regular, overage = calculate_metric_charge(
            usage,
            tiers,
        )

        customer_id = usage["customer_id"]

        charges[customer_id]["usage_charge"] += regular

        charges[customer_id]["overage_charge"] += overage

    for customer_id in charges:

        charges[customer_id]["usage_charge"] = money(
            charges[customer_id]["usage_charge"]
        )

        charges[customer_id]["overage_charge"] = money(
            charges[customer_id]["overage_charge"]
        )

    return charges


# --------------------------------------------------
# 7. COMMITMENT DISCOUNT AND TOP-UP
# --------------------------------------------------

def calculate_commitment(customer, usage_charge):

    commitment = Decimal(
        customer["monthly_commitment"]
    )

    if commitment <= 0:
        return {
            "commitment_discount": Decimal("0"),
            "commitment_topup": Decimal("0"),
            "base_charge": money(usage_charge),
            "rollover_created": Decimal("0"),
        }

    discounted_usage = money(
        usage_charge * Decimal("0.85")
    )

    commitment_discount = money(
        usage_charge - discounted_usage
    )

    commitment_topup = max(
        Decimal("0"),
        commitment - discounted_usage,
    )

    base_charge = max(
        discounted_usage,
        commitment,
    )

    rollover_created = commitment_topup

    return {
        "commitment_discount": commitment_discount,
        "commitment_topup": money(commitment_topup),
        "base_charge": money(base_charge),
        "rollover_created": money(rollover_created),
    }


# --------------------------------------------------
# 8. COMMITMENT ROLLOVER
# --------------------------------------------------

def calculate_rollover_usage(
    rollover_created,
    next_month_overage,
):

    rollover_used = min(
        rollover_created,
        next_month_overage,
    )

    adjusted_overage = max(
        Decimal("0"),
        next_month_overage - rollover_used,
    )

    return {
        "rollover_used": money(rollover_used),
        "adjusted_overage": money(adjusted_overage),
    }


# --------------------------------------------------
# 9. SLA CREDIT CALCULATION
# --------------------------------------------------

def calculate_sla_percentage(uptime):
    """
    Threshold bands inferred from the supplied examples:
    below 95%: 50% credit
    95% to below 99.900%: 10% credit
    99.900% or above: 0% credit

    Verify these inferred bands against the official
    SLA policy if a complete threshold table is provided.
    """

    if uptime < Decimal("95.000"):
        return Decimal("50")

    if uptime < Decimal("99.900"):
        return Decimal("10")

    return Decimal("0")


def calculate_sla_credit(
    customer_id,
    previous_month,
    previous_base_charge,
    current_base_charge,
    uptime_records,
):

    uptime = uptime_records.get(
        (customer_id, previous_month)
    )

    if uptime is None:
        return Decimal("0")

    credit_percentage = calculate_sla_percentage(uptime)

    requested_credit = money(
        previous_base_charge
        * credit_percentage
        / Decimal("100")
    )

    return money(
        min(requested_credit, current_base_charge)
    )


# --------------------------------------------------
# 10. GST CALCULATION
# --------------------------------------------------

def calculate_gst(customer, net):

    gst_amount = money(
        net * Decimal("0.18")
    )

    state = customer.get(
        "state",
        customer.get("billing_state", ""),
    )

    if state.strip().lower() == "karnataka":

        cgst = money(
            net * Decimal("0.09")
        )

        sgst = money(
            net * Decimal("0.09")
        )

        return {
            "gst": gst_amount,
            "cgst": cgst,
            "sgst": sgst,
            "igst": Decimal("0"),
        }

    return {
        "gst": gst_amount,
        "cgst": Decimal("0"),
        "sgst": Decimal("0"),
        "igst": gst_amount,
    }


# --------------------------------------------------
# 11. MONTH HELPERS
# --------------------------------------------------

def previous_month(month):

    current = datetime.strptime(
        month + "-01",
        "%Y-%m-%d",
    )

    previous = current - timedelta(days=1)

    return previous.strftime("%Y-%m")


def calculate_month_charges(
    records,
    month,
    cutoff,
    metrics,
    customers,
    price_books,
):

    usage_rows = aggregate_invoice_usage(
        records,
        month,
        cutoff,
        metrics,
    )

    return calculate_usage_charges(
        usage_rows,
        customers,
        price_books,
    )


# --------------------------------------------------
# 12. MAIN INVOICE GENERATION
# --------------------------------------------------


def create_invoice_state():
    return {
        "metrics": load_metrics(),
        "customers": load_customers(),
        "price_books": load_price_books(),
        "uptime_records": load_uptime(),
        "invoice_rows": [],
        "previous_month_results": {},
        "cutoffs": {},
    }


def generate_invoice_month(state, month, run_ts):

    cutoff = datetime.strptime(
        run_ts,
        "%Y-%m-%d %H:%M:%S",
    )

    if month in state["cutoffs"]:
        raise ValueError(
            f"Invoice already generated for {month}"
        )

    # Load only events ingested before this invoice cutoff.
    records = load_event_records(
        allow_pending=True,
        cutoff=cutoff,
    )

    metrics = state["metrics"]
    customers = state["customers"]
    price_books = state["price_books"]
    uptime_records = state["uptime_records"]

    invoice_rows = state["invoice_rows"]
    previous_month_results = state["previous_month_results"]
    cutoffs = state["cutoffs"]

    # Calculate this month's usage charges.
    current_charges = calculate_month_charges(
        records,
        month,
        cutoff,
        metrics,
        customers,
        price_books,
    )

    prior_month = previous_month(month)

    prior_base_charges = {}
    prior_rollovers = {}

    if prior_month in previous_month_results:

        prior_results = previous_month_results[prior_month]

        prior_base_charges = prior_results["base"]
        prior_rollovers = prior_results["rollover"]

    # --------------------------------------------------
    # LATE EVENT ADJUSTMENTS
    # --------------------------------------------------

    adjustments = defaultdict(
        lambda: Decimal("0")
    )

    if prior_month in cutoffs:

        previous_cutoff = cutoffs[prior_month]

        previous_at_invoice = calculate_month_charges(
            records,
            prior_month,
            previous_cutoff,
            metrics,
            customers,
            price_books,
        )

        previous_at_current_cutoff = calculate_month_charges(
            records,
            prior_month,
            cutoff,
            metrics,
            customers,
            price_books,
        )

        for customer_id in customers:

            before = previous_at_invoice.get(
                customer_id,
                {
                    "usage_charge": Decimal("0"),
                    "overage_charge": Decimal("0"),
                },
            )

            after = previous_at_current_cutoff.get(
                customer_id,
                {
                    "usage_charge": Decimal("0"),
                    "overage_charge": Decimal("0"),
                },
            )

            adjustments[customer_id] = money(
                after["usage_charge"]
                + after["overage_charge"]
                - before["usage_charge"]
                - before["overage_charge"]
            )

    # --------------------------------------------------
    # CREATE CUSTOMER INVOICES
    # --------------------------------------------------

    current_base_results = {}
    current_rollover_results = {}

    for customer_id, customer in sorted(customers.items()):

        charges = current_charges.get(
            customer_id,
            {
                "usage_charge": Decimal("0"),
                "overage_charge": Decimal("0"),
            },
        )

        usage_charge = money(
            charges["usage_charge"]
        )

        overage_charge = money(
            charges["overage_charge"]
        )

        # Commitment discount and top-up.
        commitment = calculate_commitment(
            customer,
            usage_charge,
        )

        base_charge = commitment["base_charge"]
        rollover_created = commitment["rollover_created"]

        # Previous month's rollover.
        previous_rollover = prior_rollovers.get(
            customer_id,
            Decimal("0"),
        )

        rollover = calculate_rollover_usage(
            previous_rollover,
            overage_charge,
        )

        rollover_used = rollover["rollover_used"]

        # Previous month's SLA credit.
        sla_credit = calculate_sla_credit(
            customer_id,
            prior_month,
            prior_base_charges.get(
                customer_id,
                Decimal("0"),
            ),
            base_charge,
            uptime_records,
        )

        adjustment = adjustments[customer_id]

        # Apply credits before minimum invoice amount.
        amount_before_minimum = (
            base_charge
            + overage_charge
            + adjustment
            - rollover_used
            - sla_credit
        )

        net = money(
            max(
                Decimal("100"),
                amount_before_minimum,
            )
        )

        # GST.
        gst_details = calculate_gst(
            customer,
            net,
        )

        gst = gst_details["gst"]

        # Final amount rounded to nearest rupee.
        total = (net + gst).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )

        invoice_rows.append({

            "customer_id": customer_id,
            "month": month,
            "usage_charge": f"{usage_charge:.2f}",
            "commitment_discount": (
                f"{commitment['commitment_discount']:.2f}"
            ),
            "commitment_topup": (
                f"{commitment['commitment_topup']:.2f}"
            ),
            "base_charge": f"{base_charge:.2f}",
            "overage_charge": f"{overage_charge:.2f}",
            "adjustments": f"{adjustment:.2f}",
            "sla_credit": f"{sla_credit:.2f}",
            "net": f"{net:.2f}",
            "gst": f"{gst:.2f}",
            "total_rounded": f"{total:.2f}",
            "rollover_created": f"{rollover_created:.2f}",
            "rollover_used": f"{rollover_used:.2f}",
        })

        current_base_results[customer_id] = base_charge

        current_rollover_results[customer_id] = (
            rollover_created
        )

    # Preserve results for the next month's credits and rollover.
    previous_month_results[month] = {
        "base": current_base_results,
        "rollover": current_rollover_results,
    }

    # Remember this month's invoice cutoff.
    cutoffs[month] = cutoff

    # Save cumulative invoices after each invoice command.
    save_csv(
        OUTPUT / "invoices.csv",
        invoice_rows,
        INVOICE_COLUMNS,
    )

    print(f"Generated invoices for {month}: {len(customers)}")


def generate_invoices():

    state = create_invoice_state()

    cutoffs = load_invoice_cutoffs()

    for month in sorted(cutoffs):

        run_ts = cutoffs[month].strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        generate_invoice_month(
            state,
            month,
            run_ts,
        )

    print(f"Generated invoices: {len(state['invoice_rows'])}")

    print(
        f"Output: {OUTPUT / 'invoices.csv'}"
    )

# --------------------------------------------------
# 14. PROGRAM ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    generate_invoices()
