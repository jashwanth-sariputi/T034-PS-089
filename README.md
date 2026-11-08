# PS-089: API Usage Metering, Tiered Pricing and Overage Engine

**Team:** T034  
**Project:** API Usage Metering, Tiered Pricing and Overage Engine  
**Language:** Python

## 1. Project Overview

PS-089 is a Python-based API usage metering and billing platform designed to process customer API consumption, enforce usage limits, calculate charges using tiered pricing, and generate monthly invoices.

The system processes usage events in chronological ingestion order and applies validation, idempotency, quota enforcement, rate limiting, usage aggregation, pricing, and billing rules.

## 2. Key Features

- Usage event ingestion and validation.
- Duplicate event detection using idempotency keys.
- Late and future event validation.
- API usage quota enforcement.
- Rolling-window rate limiting and burst allowance.
- Usage aggregation for API calls, storage, and active users.
- Volume, graduated, and flat pricing models.
- Monthly commitment and rollover calculations.
- SLA credit calculations.
- GST calculation and invoice generation.
- CSV reports for event decisions, usage, rating, and invoices.
- Streamlit customer registration, login, and account dashboard.

## 3. Technology Stack

- Python
- SQLite
- Streamlit
- Pandas
- Pytest
- Bcrypt

## 4. Project Structure

```text
T034-PS-089/
│
├── app.py
├── requirements.txt
├── .gitignore
│
├── config/
│   ├── customers.json
│   ├── metrics.json
│   └── price_books.json
│
├── data/
│   └── ps089.db
│
├── input/
│   └── T034-Dataset/
│       ├── commands.txt
│       ├── customers.csv
│       ├── price_books.csv
│       ├── uptime.csv
│       ├── usage_events.csv
│       └── README.md
│
├── output/
│   ├── event_decisions.csv
│   ├── usage_summary.csv
│   ├── rating_breakdown.csv
│   └── invoices.csv
│
├── src/
│   ├── auth.py
│   ├── command_runner.py
│   ├── csv_ingestion.py
│   ├── customer_registration.py
│   ├── database.py
│   ├── invoice_engine.py
│   ├── rating_engine.py
│   ├── registration.py
│   ├── usage_aggregation.py
│   └── usage_ingestion.py
│
└── tests/
    ├── test_command_runner.py
    ├── test_event_processing.py
    ├── test_invoice_engine.py
    └── test_usage_engine.py
```

## 5. Installation

Clone the repository:

```bash
git clone https://github.com/jashwanth-sariputi/T034-PS-089.git
cd T034-PS-089
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## 6. Running the Project

### Run the billing engine

```bash
python -m src.command_runner
```

The command runner reads `input/T034-Dataset/commands.txt` and executes commands in their specified order.

Supported commands:

- `OPEN_MONTH`
- `INGEST_UNTIL`
- `GENERATE_INVOICES`
- `PRINT_USAGE`
- `PRINT_INVOICE`
- `PRINT_THROTTLE_LOG`

### Run the Streamlit application

```bash
python -m streamlit run app.py
```

The current application provides customer registration, login, and a basic account dashboard.

## 7. Generated Reports

The billing engine generates four CSV reports:

| Report | Purpose |
|---|---|
| `event_decisions.csv` | Event processing, metering, throttling, and blocking decisions |
| `usage_summary.csv` | Aggregated monthly customer usage |
| `rating_breakdown.csv` | Pricing calculations by metric and tier |
| `invoices.csv` | Monthly invoice calculations and totals |

## 8. Testing

Run the test suite:

```bash
python -m pytest -v
```

The current test suite covers event processing, quota and rate-limit behavior, usage calculations, invoice calculations, commitment handling, SLA credits, and GST.

## 9. Project Objective

The objective is to build a reliable and testable API usage metering and billing engine that can process usage events, enforce customer plans, calculate tier-based charges, and generate accurate monthly billing reports.

---

**Repository:** https://github.com/jashwanth-sariputi/T034-PS-089
