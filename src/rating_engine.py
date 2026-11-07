import csv
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input" / "T034-Dataset"
OUTPUT = ROOT / "output"

CUSTOMERS_FILE = INPUT / "customers.csv"
PRICE_BOOKS_FILE = INPUT / "price_books.csv"
USAGE_FILE = OUTPUT / "usage_summary.csv"
RATING_FILE = OUTPUT / "rating_breakdown.csv"

COLUMNS = [
    "customer_id",
    "month",
    "metric_id",
    "tier_type",
    "band_from",
    "band_to",
    "quantity",
    "unit_price",
    "amount",
]


def load_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def save_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def load_customers():
    customers = {}

    for row in load_csv(CUSTOMERS_FILE):
        customers[row["customer_id"]] = row

    return customers


def load_price_books():
    price_books = defaultdict(list)

    for row in load_csv(PRICE_BOOKS_FILE):
        price_books[
            (row["price_book_id"], row["metric_id"])
        ].append(row)

    for tiers in price_books.values():
        tiers.sort(key=lambda tier: int(tier["tier_from"]))

    return price_books


def create_rating_row(
    usage,
    tier,
    quantity,
    unit_price,
):
    amount = money(quantity * unit_price)

    return {
        "customer_id": usage["customer_id"],
        "month": usage["month"],
        "metric_id": usage["metric_id"],
        "tier_type": tier["tier_type"],
        "band_from": tier["tier_from"],
        "band_to": tier["tier_to"],
        "quantity": str(quantity),
        "unit_price": str(unit_price),
        "amount": str(amount),
    }


def rate_volume(usage, tiers):
    billable = Decimal(usage["billable_quantity"])
    overage = Decimal(usage["overage_quantity"])

    if billable <= 0:
        return []

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
            f"No volume tier found for {usage['customer_id']} "
            f"{usage['metric_id']} quantity {billable}"
        )

    unit_price = Decimal(tier["unit_price"])

    # Only overage units receive the configured multiplier.
    multiplier = Decimal(tier["overage_multiplier"] or "1")

    regular_quantity = billable - overage

    rows = []

    if regular_quantity > 0:
        rows.append(
            create_rating_row(
                usage,
                tier,
                regular_quantity,
                unit_price,
            )
        )

    if overage > 0:
        rows.append(
            create_rating_row(
                usage,
                tier,
                overage,
                unit_price * multiplier,
            )
        )

    return rows


def rate_graduated(usage, tiers):
    billable = Decimal(usage["billable_quantity"])
    overage = Decimal(usage["overage_quantity"])

    if billable <= 0:
        return []

    regular_quantity = billable - overage
    rows = []

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
                regular_quantity - lower,
            )
        else:
            quantity = max(
                Decimal("0"),
                min(regular_quantity, upper) - lower + (Decimal("1") if lower > 0 else Decimal("0")),
            )

        if quantity > 0:
            rows.append(
                create_rating_row(
                    usage,
                    tier,
                    quantity,
                    Decimal(tier["unit_price"]),
                )
            )

    if overage > 0:
        top_tier = tiers[-1]
        multiplier = Decimal(
            top_tier["overage_multiplier"] or "1"
        )

        rows.append(
            create_rating_row(
                usage,
                top_tier,
                overage,
                Decimal(top_tier["unit_price"]) * multiplier,
            )
        )

    return rows


def rate_flat(usage, tiers):
    billable = Decimal(usage["billable_quantity"])

    if billable <= 0:
        return []

    tier = tiers[0]
    unit_price = Decimal(tier["unit_price"])

    return [
        create_rating_row(
            usage,
            tier,
            billable,
            unit_price,
        )
    ]


def generate_ratings():
    customers = load_customers()
    price_books = load_price_books()
    usage_rows = load_csv(USAGE_FILE)

    output_rows = []

    for usage in usage_rows:
        customer_id = usage["customer_id"]

        if customer_id not in customers:
            raise ValueError(
                f"Unknown customer: {customer_id}"
            )

        customer = customers[customer_id]

        price_book_id = customer["price_book_id"]
        metric_id = usage["metric_id"]

        tiers = price_books.get(
            (price_book_id, metric_id)
        )

        if not tiers:
            raise ValueError(
                f"Missing pricing: {price_book_id}, {metric_id}"
            )

        tier_type = tiers[0]["tier_type"]

        if tier_type == "VOLUME":
            rows = rate_volume(usage, tiers)

        elif tier_type == "GRADUATED":
            rows = rate_graduated(usage, tiers)

        elif tier_type == "FLAT":
            rows = rate_flat(usage, tiers)

        else:
            raise ValueError(
                f"Unsupported tier type: {tier_type}"
            )

        output_rows.extend(rows)

    output_rows.sort(
        key=lambda row: (
            row["customer_id"],
            row["month"],
            row["metric_id"],
            int(row["band_from"]),
        )
    )

    save_csv(RATING_FILE, output_rows, COLUMNS)

    print(f"Rated usage records: {len(usage_rows)}")
    print(f"Rating breakdown rows: {len(output_rows)}")
    print(f"Output: {RATING_FILE}")


if __name__ == "__main__":
    generate_ratings()
