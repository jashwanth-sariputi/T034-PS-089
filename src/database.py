
import sqlite3
from pathlib import Path

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database location
DATABASE_PATH = BASE_DIR / "data" / "ps089.db"


def get_connection():
    """Create and return a SQLite database connection."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database():
    """Create all required PS-089 database tables."""

    schema = [

        # 1. Registered usage metrics
        """
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_code TEXT NOT NULL UNIQUE,
            metric_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            aggregation_type TEXT NOT NULL
                CHECK (aggregation_type IN ('SUM', 'MAX_AVG', 'UNIQUE')),
            rounding_precision INTEGER NOT NULL DEFAULT 0,
            free_allowance REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # 2. Pricing books
        """
        CREATE TABLE IF NOT EXISTS price_books (
            price_book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            price_book_code TEXT NOT NULL UNIQUE,
            price_book_name TEXT NOT NULL,
            tier_type TEXT NOT NULL
                CHECK (tier_type IN ('VOLUME', 'GRADUATED')),
            currency TEXT NOT NULL DEFAULT 'INR',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # 3. Individual pricing tiers
        """
        CREATE TABLE IF NOT EXISTS price_tiers (
            tier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            price_book_id INTEGER NOT NULL,
            lower_limit INTEGER NOT NULL,
            upper_limit INTEGER,
            unit_price TEXT NOT NULL,
            FOREIGN KEY (price_book_id)
                REFERENCES price_books(price_book_id),
            CHECK (lower_limit >= 0)
        )
        """,

        # 4. Customers
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT,
            plan_name TEXT NOT NULL
                CHECK (plan_name IN ('STARTER', 'GROWTH', 'SCALE')),
            monthly_quota INTEGER NOT NULL,
            overage_enabled INTEGER NOT NULL DEFAULT 0,
            price_book_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (price_book_id)
                REFERENCES price_books(price_book_id)
        )
        """,

        # 5. Incoming usage events
        """
        CREATE TABLE IF NOT EXISTS usage_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            metric_code TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            ingestion_timestamp TEXT NOT NULL,
            quantity REAL NOT NULL,
            event_status TEXT NOT NULL,
            rejection_reason TEXT,
            is_overage INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        )
        """,

        # 6. Hourly aggregated usage
        """
        CREATE TABLE IF NOT EXISTS hourly_usage (
            hourly_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            metric_code TEXT NOT NULL,
            hour_start TEXT NOT NULL,
            aggregated_value REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),
            UNIQUE (customer_id, metric_code, hour_start)
        )
        """,

        # 7. Rate-limit decisions
        """
        CREATE TABLE IF NOT EXISTS rate_limit_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            event_id INTEGER,
            decision TEXT NOT NULL,
            reason TEXT,
            decision_timestamp TEXT NOT NULL,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),
            FOREIGN KEY (event_id)
                REFERENCES usage_events(event_id)
        )
        """,

        # 8. Monthly customer commitments
        """
        CREATE TABLE IF NOT EXISTS commitments (
            commitment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            billing_month TEXT NOT NULL,
            commitment_amount TEXT NOT NULL,
            discount_percentage TEXT NOT NULL DEFAULT '15',
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),
            UNIQUE (customer_id, billing_month)
        )
        """,

        # 9. Commitment rollover ledger
        """
        CREATE TABLE IF NOT EXISTS rollover_ledger (
            rollover_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            source_month TEXT NOT NULL,
            expiry_month TEXT NOT NULL,
            rollover_amount TEXT NOT NULL,
            amount_used TEXT NOT NULL DEFAULT '0',
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        )
        """,

        # 10. SLA uptime records
        """
        CREATE TABLE IF NOT EXISTS sla_records (
            sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            billing_month TEXT NOT NULL,
            uptime_percentage TEXT NOT NULL,
            credit_percentage TEXT NOT NULL DEFAULT '0',
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),
            UNIQUE (customer_id, billing_month)
        )
        """,

        # 11. Monthly invoices
        """
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL UNIQUE,
            customer_id TEXT NOT NULL,
            billing_month TEXT NOT NULL,
            usage_charge TEXT NOT NULL DEFAULT '0',
            commitment_charge TEXT NOT NULL DEFAULT '0',
            overage_charge TEXT NOT NULL DEFAULT '0',
            sla_credit TEXT NOT NULL DEFAULT '0',
            adjustment_amount TEXT NOT NULL DEFAULT '0',
            gst_amount TEXT NOT NULL DEFAULT '0',
            final_amount TEXT NOT NULL DEFAULT '0',
            invoice_status TEXT NOT NULL DEFAULT 'DRAFT',
            generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),
            UNIQUE (customer_id, billing_month)
        )
        """,

        # 12. Invoice line-item breakdown
        """
        CREATE TABLE IF NOT EXISTS invoice_lines (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            metric_code TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            unit_price TEXT NOT NULL DEFAULT '0',
            amount TEXT NOT NULL DEFAULT '0',
            FOREIGN KEY (invoice_id)
                REFERENCES invoices(invoice_id)
        )
        """,

        # 13. Billing adjustments
        """
        CREATE TABLE IF NOT EXISTS billing_adjustments (
            adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            original_billing_month TEXT NOT NULL,
            adjustment_month TEXT NOT NULL,
            amount TEXT NOT NULL,
            description TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        )
        """,

        # 14. Audit logs
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # 15. Processing run history
        """
        CREATE TABLE IF NOT EXISTS processing_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL,
            billing_month TEXT,
            run_status TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            details TEXT
        )
        """,

        # 16. Monthly usage summary
        """
        CREATE TABLE IF NOT EXISTS monthly_usage (
            monthly_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            metric_code TEXT NOT NULL,
            billing_month TEXT NOT NULL,
            total_usage REAL NOT NULL DEFAULT 0,
            free_usage REAL NOT NULL DEFAULT 0,
            chargeable_usage REAL NOT NULL DEFAULT 0,
            overage_usage REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),
            UNIQUE (customer_id, metric_code, billing_month)
        )
        """
    ]

    indexes = [
        """
        CREATE INDEX IF NOT EXISTS idx_events_customer_time
        ON usage_events(customer_id, event_timestamp)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_events_idempotency
        ON usage_events(customer_id, idempotency_key, ingestion_timestamp)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_hourly_customer_time
        ON hourly_usage(customer_id, hour_start)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_invoices_month
        ON invoices(billing_month)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_audit_created
        ON audit_logs(created_at)
        """
    ]

   
    with get_connection() as connection:
        for statement in schema:
            connection.execute(statement)

        for statement in indexes:
            connection.execute(statement)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
            )
        """)


    print("PS-089 database initialized successfully!")
    print(f"Database location: {DATABASE_PATH}")


def get_table_names():
    """Return all tables created in the database."""

    with get_connection() as connection:
        result = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

    return [row["name"] for row in result]

    


if __name__ == "__main__":
    initialize_database()

    print("\nCreated database tables:")

    for table in get_table_names():
        print(f" - {table}")

    print(f"\nTotal tables: {len(get_table_names())}")
