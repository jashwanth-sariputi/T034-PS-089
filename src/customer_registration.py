
import json
from database import get_connection, BASE_DIR

CONFIG_PATH = BASE_DIR / "config" / "customers.json"

VALID_PLANS = {
    "STARTER": 100000,
    "GROWTH": 1000000,
    "SCALE": 10000000
}


def register_customers():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = json.load(file)

    customers = config.get("customers", [])

    if not customers:
        raise ValueError("No customers found in configuration.")

    registered = 0

    with get_connection() as connection:

        for customer in customers:
            customer_id = customer["customer_id"]
            customer_name = customer["customer_name"]
            email = customer["email"]
            plan = customer["plan_name"].upper()
            quota = customer["monthly_quota"]
            overage = customer["overage_enabled"]
            price_book_code = customer["price_book_code"]

            if plan not in VALID_PLANS:
                raise ValueError(f"Invalid plan: {plan}")

            if quota != VALID_PLANS[plan]:
                raise ValueError(
                    f"Incorrect quota for {plan}: expected "
                    f"{VALID_PLANS[plan]}"
                )

            if not isinstance(overage, bool):
                raise ValueError("Overage enabled must be true or false.")

            price_book = connection.execute(
                """
                SELECT price_book_id
                FROM price_books
                WHERE price_book_code = ?
                """,
                (price_book_code,)
            ).fetchone()

            if price_book is None:
                raise ValueError(
                    f"Price book not found: {price_book_code}"
                )

            connection.execute(
                """
                INSERT INTO customers (
                    customer_id,
                    customer_name,
                    email,
                    plan_name,
                    monthly_quota,
                    overage_enabled,
                    price_book_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(customer_id) DO UPDATE SET
                    customer_name = excluded.customer_name,
                    email = excluded.email,
                    plan_name = excluded.plan_name,
                    monthly_quota = excluded.monthly_quota,
                    overage_enabled = excluded.overage_enabled,
                    price_book_id = excluded.price_book_id
                """,
                (
                    customer_id,
                    customer_name,
                    email,
                    plan,
                    quota,
                    int(overage),
                    price_book["price_book_id"]
                )
            )

            registered += 1

    print(f"\nSuccessfully registered {registered} customers.")


def show_customers():
    with get_connection() as connection:
        customers = connection.execute(
            """
            SELECT
                customer_id,
                customer_name,
                email,
                plan_name,
                monthly_quota,
                overage_enabled
            FROM customers
            ORDER BY customer_id
            """
        ).fetchall()

    print("\n========== REGISTERED CUSTOMERS ==========")

    for customer in customers:
        print(
            f"\nID: {customer['customer_id']}"
            f"\nName: {customer['customer_name']}"
            f"\nEmail: {customer['email']}"
            f"\nPlan: {customer['plan_name']}"
            f"\nMonthly quota: {customer['monthly_quota']:,}"
            f"\nOverage: "
            f"{'Enabled' if customer['overage_enabled'] else 'Disabled'}"
        )


if __name__ == "__main__":
    print("Starting customer registration...")
    register_customers()
    show_customers()
    print("\nCustomer registration completed!")
