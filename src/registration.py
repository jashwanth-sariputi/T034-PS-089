
import json
from decimal import Decimal, InvalidOperation

from database import get_connection, BASE_DIR

CONFIG_DIR = BASE_DIR / "config"


def load_json(filename):
    file_path = CONFIG_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def register_metrics():
    config = load_json("metrics.json")
    metrics = config.get("metrics", [])

    if len(metrics) != 3:
        raise ValueError("Exactly three metrics are expected.")

    allowed = {"SUM", "MAX_AVG", "UNIQUE"}

    with get_connection() as connection:
        for metric in metrics:
            if metric["aggregation_type"] not in allowed:
                raise ValueError("Invalid aggregation type.")

            connection.execute(
                """
                INSERT INTO metrics (
                    metric_code, metric_name, unit,
                    aggregation_type, rounding_precision,
                    free_allowance
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_code) DO UPDATE SET
                    metric_name = excluded.metric_name,
                    unit = excluded.unit,
                    aggregation_type = excluded.aggregation_type,
                    rounding_precision = excluded.rounding_precision,
                    free_allowance = excluded.free_allowance
                """,
                (
                    metric["metric_code"],
                    metric["metric_name"],
                    metric["unit"],
                    metric["aggregation_type"],
                    metric["rounding_precision"],
                    metric["free_allowance"]
                )
            )

    print(f"Successfully registered {len(metrics)} metrics.")


def register_price_books():
    config = load_json("price_books.json")
    books = config.get("price_books", [])

    with get_connection() as connection:
        for book in books:
            if book["tier_type"] not in {"VOLUME", "GRADUATED"}:
                raise ValueError("Invalid pricing tier type.")

            tiers = book.get("tiers", [])

            if not tiers:
                raise ValueError("Pricing tiers are missing.")

            previous_upper = None

            for index, tier in enumerate(tiers):
                lower = tier["lower_limit"]
                upper = tier["upper_limit"]

                try:
                    price = Decimal(str(tier["unit_price"]))
                except InvalidOperation:
                    raise ValueError("Invalid unit price.")

                if lower < 0 or price < 0:
                    raise ValueError("Negative limits or prices are invalid.")

                if upper is not None and upper < lower:
                    raise ValueError("Invalid tier range.")

                if index > 0 and lower != previous_upper + 1:
                    raise ValueError("Pricing tiers must be continuous.")

                if index < len(tiers) - 1 and upper is None:
                    raise ValueError("Only the final tier can be unlimited.")

                previous_upper = upper

            if tiers[-1]["upper_limit"] is not None:
                raise ValueError("Final tier must be unlimited.")

            connection.execute(
                """
                INSERT INTO price_books (
                    price_book_code, price_book_name,
                    tier_type, currency
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(price_book_code) DO UPDATE SET
                    price_book_name = excluded.price_book_name,
                    tier_type = excluded.tier_type,
                    currency = excluded.currency
                """,
                (
                    book["price_book_code"],
                    book["price_book_name"],
                    book["tier_type"],
                    book["currency"]
                )
            )

            row = connection.execute(
                """
                SELECT price_book_id FROM price_books
                WHERE price_book_code = ?
                """,
                (book["price_book_code"],)
            ).fetchone()

            price_book_id = row["price_book_id"]

            connection.execute(
                "DELETE FROM price_tiers WHERE price_book_id = ?",
                (price_book_id,)
            )

            for tier in tiers:
                connection.execute(
                    """
                    INSERT INTO price_tiers (
                        price_book_id, lower_limit,
                        upper_limit, unit_price
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        price_book_id,
                        tier["lower_limit"],
                        tier["upper_limit"],
                        str(Decimal(str(tier["unit_price"])))
                    )
                )

    print(f"Successfully registered {len(books)} price books.")


def show_registration_summary():
    with get_connection() as connection:
        metrics = connection.execute(
            "SELECT * FROM metrics ORDER BY metric_code"
        ).fetchall()

        books = connection.execute(
            "SELECT * FROM price_books ORDER BY price_book_code"
        ).fetchall()

        print("\n========== REGISTERED METRICS ==========")

        for metric in metrics:
            print(
                f"{metric['metric_code']} | {metric['unit']} | "
                f"{metric['aggregation_type']} | "
                f"Free: {metric['free_allowance']}"
            )

        print("\n========== REGISTERED PRICE BOOKS ==========")

        for book in books:
            print(f"\n{book['price_book_code']} ({book['tier_type']})")

            tiers = connection.execute(
                """
                SELECT lower_limit, upper_limit, unit_price
                FROM price_tiers
                WHERE price_book_id = ?
                ORDER BY lower_limit
                """,
                (book["price_book_id"],)
            ).fetchall()

            for tier in tiers:
                upper = (
                    tier["upper_limit"]
                    if tier["upper_limit"] is not None
                    else "Unlimited"
                )

                print(
                    f"  {tier['lower_limit']} - {upper}: "
                    f"Rs. {tier['unit_price']}"
                )


def run_registration():
    print("Starting PS-089 registration...")

    register_metrics()
    register_price_books()
    show_registration_summary()

    print("\nRegistration completed successfully!")


if __name__ == "__main__":
    run_registration()
