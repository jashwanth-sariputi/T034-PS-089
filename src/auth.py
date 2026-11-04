
import uuid
import sqlite3
import bcrypt

from .database import get_connection


PLAN_QUOTAS = {
    "STARTER": 100_000,
    "GROWTH": 1_000_000,
    "SCALE": 10_000_000
}


def register_customer(name, email, password, plan_name):
    """Register a new customer and create their secure login account."""

    name = name.strip()
    email = email.strip().lower()
    plan_name = plan_name.strip().upper()

    # Validate registration details
    if not name or not email or not password:
        raise ValueError("All fields are required.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    if plan_name not in PLAN_QUOTAS:
        raise ValueError("Please select a valid plan.")

    # Generate a unique customer ID
    customer_id = "CUST" + uuid.uuid4().hex[:12].upper()

    # Securely hash the password
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    try:
        with get_connection() as connection:

            # Check whether email already exists
            existing_email = connection.execute(
                """
                SELECT 1 FROM accounts
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

            if existing_email:
                raise ValueError(
                    "This email is already registered. Please log in."
                )

            # Get the default price book
            price_book = connection.execute(
                """
                SELECT price_book_id
                FROM price_books
                WHERE price_book_code = ?
                """,
                ("API_VOLUME",)
            ).fetchone()

            if price_book is None:
                raise ValueError(
                    "Default price book is not configured."
                )

            # Register customer
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
                """,
                (
                    customer_id,
                    name,
                    email,
                    plan_name,
                    PLAN_QUOTAS[plan_name],
                    0,
                    price_book["price_book_id"]
                )
            )

            # Create login account
            connection.execute(
                """
                INSERT INTO accounts (
                    customer_id,
                    email,
                    password_hash
                )
                VALUES (?, ?, ?)
                """,
                (
                    customer_id,
                    email,
                    password_hash
                )
            )

        return customer_id

    except sqlite3.IntegrityError:
        raise ValueError(
            "This email is already registered. Please use another email."
        )


def authenticate_user(email, password):
    """Verify login credentials and return the customer's ID."""

    with get_connection() as connection:

        account = connection.execute(
            """
            SELECT customer_id, password_hash, is_active
            FROM accounts
            WHERE email = ?
            """,
            (email.strip().lower(),)
        ).fetchone()

    if account is None or account["is_active"] != 1:
        return None

    stored_hash = account["password_hash"].encode("utf-8")

    if bcrypt.checkpw(
        password.encode("utf-8"),
        stored_hash
    ):
        return account["customer_id"]

    return None
