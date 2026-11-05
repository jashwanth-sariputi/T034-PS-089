
from datetime import datetime, timezone, timedelta

from .database import get_connection


def parse_utc_timestamp(value):
    """Parse a timestamp and normalize it to UTC."""
    if isinstance(value, datetime):
        timestamp = value
    else:
        try:
            timestamp = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            raise ValueError("Invalid timestamp format")

    if timestamp.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")

    return timestamp.astimezone(timezone.utc)


def ingest_usage_event(
    customer_id,
    metric_code,
    idempotency_key,
    event_timestamp,
    quantity,
    ingestion_timestamp=None
):
    """
    Ingest one usage event according to BR-01.

    Returns a dictionary containing the event status and event ID.
    """

    if not customer_id or not metric_code or not idempotency_key:
        raise ValueError("Customer, metric and idempotency key are required")

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be numeric")

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")

    event_time = parse_utc_timestamp(event_timestamp)

    if ingestion_timestamp is None:
        ingestion_time = datetime.now(timezone.utc)
    else:
        ingestion_time = parse_utc_timestamp(ingestion_timestamp)

    if event_time > ingestion_time + timedelta(minutes=5):
        status = "REJECTED_FUTURE"
        reason = "Event timestamp is more than 5 minutes in the future"

    elif event_time < ingestion_time - timedelta(hours=72):
        status = "REJECTED_LATE"
        reason = "Event timestamp is more than 72 hours old"

    else:
        status = "ACCEPTED"
        reason = None

    with get_connection() as connection:

        customer = connection.execute(
            "SELECT customer_id FROM customers WHERE customer_id = ?",
            (customer_id,)
        ).fetchone()

        if customer is None:
            raise ValueError("Customer does not exist")

        metric = connection.execute(
            "SELECT metric_code FROM metrics WHERE metric_code = ?",
            (metric_code,)
        ).fetchone()

        if metric is None:
            raise ValueError("Metric does not exist")

        if status == "ACCEPTED":
            duplicate = connection.execute(
                """
                SELECT event_id
                FROM usage_events
                WHERE customer_id = ?
                  AND idempotency_key = ?
                  AND event_status = 'ACCEPTED'
                  AND ingestion_timestamp >= ?
                ORDER BY ingestion_timestamp DESC
                LIMIT 1
                """,
                (
                    customer_id,
                    idempotency_key,
                    (ingestion_time - timedelta(hours=24)).isoformat()
                )
            ).fetchone()

            if duplicate:
                status = "DUPLICATE"
                reason = "Idempotency key already used within 24 hours"

        cursor = connection.execute(
            """
            INSERT INTO usage_events (
                customer_id,
                metric_code,
                idempotency_key,
                event_timestamp,
                ingestion_timestamp,
                quantity,
                event_status,
                rejection_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                metric_code,
                idempotency_key,
                event_time.isoformat(),
                ingestion_time.isoformat(),
                quantity,
                status,
                reason
            )
        )

        return {
            "event_id": cursor.lastrowid,
            "status": status,
            "reason": reason
        }
