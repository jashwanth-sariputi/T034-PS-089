# PS-089 — API Usage Metering, Tiered Pricing and Overage Engine

**Team:** T034  
**Problem Statement:** PS-089  
**Domain:** SaaS / API Billing  
**Implementation:** Python  
**Execution model:** Command-file driven terminal application  
**Testing:** pytest

---

## 1. Project Overview

PS-089 is a command-driven API usage metering and billing engine. It processes timestamped usage events for multiple API customers, validates incoming events, enforces usage policies, aggregates monthly consumption, calculates charges using configured pricing models, and generates customer invoices.

The application is executed from the terminal. It reads the supplied command sequence from:

`input/T034-Dataset/commands.txt`

The command runner processes each command in file order and prints progress, usage reports, invoice details, and throttle information in the terminal. It also generates CSV files under the `output/` directory for review and verification.

## 2. Problem Statement

SaaS providers need a reliable way to measure customer API consumption and convert that consumption into accurate monthly bills. A billing engine must do more than count requests: it must detect duplicate events, handle late or future events, enforce rate limits and plan quotas, apply free allowances, calculate tiered charges, account for commitments and overage, and apply service-level credits and taxes.

This project implements those metering and billing stages as a reproducible Python command-line workflow.

## 3. Project Objectives

- Ingest customer usage events from structured CSV data.
- Validate timestamps, quantities, customer references, and idempotency keys.
- Detect duplicate events and reject events outside the permitted time window.
- Enforce rolling rate limits, hourly burst allowances, and monthly plan quotas.
- Aggregate API calls, storage usage, and active users according to their metric rules.
- Apply free allowances and configured volume, graduated, or flat pricing.
- Calculate committed-use discounts, commitment top-ups, and rollover.
- Calculate overage charges and SLA credits.
- Apply GST and generate monthly invoices.
- Produce traceable terminal reports and CSV outputs.
- Verify business rules and edge cases with automated tests.

## 4. Scope

### Included

- CSV-based usage-event ingestion.
- Command-file execution in the order defined by the input file.
- Event validation, idempotency, late/future checks, throttling, and quota decisions.
- Monthly metric aggregation and rounding.
- Tiered rating, commitment, rollover, and overage calculations.
- SLA credit, invoice, and GST calculations.
- Terminal reports and generated CSV evidence.
- Automated unit and integration tests.

### Execution interface

The required project workflow is command-file driven and terminal based. The evaluator can run the Python command runner and inspect the processing messages and generated reports. The core billing workflow does not require a browser or graphical interface.

## 5. Core Business Rules

The engine is designed around the PS-089 business-rule requirements.

| Area | Processing rule |
|---|---|
| Idempotency and event time | Repeated idempotency keys within 24 hours are treated as duplicates. Events more than 72 hours late or more than 5 minutes in the future are rejected. |
| API rate limiting | Enforces 600 calls per rolling 60-second window and the configured hourly burst allowance. Throttled calls are not metered. |
| Plan quota | Applies the monthly API-call quota for STARTER, GROWTH, and SCALE plans. Usage beyond quota is blocked or treated as overage according to the customer's setting. |
| Free allowance | Applies the configured monthly free allowance before billable tier calculations. |
| Usage aggregation | API calls use SUM, storage uses the monthly average of hourly maximum samples, and active users use monthly unique-user counting. |
| Rounding | Monthly usage is rounded up to the configured metric precision. |
| Pricing | Supports volume, graduated, and flat price-book structures as configured in the input data. |
| Commitment | Applies the committed-use discount and minimum commitment charge, with eligible shortfall rollover rules. |
| Overage | Calculates eligible usage above quota using the configured overage multiplier. |
| SLA | Calculates service credits from the monthly uptime records and applies them to billing according to the rule set. |
| Invoice and tax | Generates monthly invoices, applies eligible adjustments and credits, calculates GST, and rounds the final invoice total. |

The detailed thresholds, input conventions, and planted scenarios are documented in `input/T034-Dataset/README.md` and the official PS-089 problem statement.

## 6. Technology Stack

- **Python 3.10+** — application logic and command execution.
- **CSV** — customer, plan, price-book, uptime, and usage-event input/output.
- **JSON** — metric configuration.
- **pytest** — automated verification.

The command-line workflow uses Python modules and the supplied data files. Run all commands from the repository root so that the relative input and output paths resolve correctly.

## 7. Project Structure

```text
T034-PS-089/
│
├── config/
│   ├── customers.json
│   ├── metrics.json
│   └── price_books.json
│
├── input/
│   └── T034-Dataset/
│       ├── commands.txt
│       ├── customers.csv
│       ├── metrics.csv
│       ├── plans.csv
│       ├── price_books.csv
│       ├── uptime.csv
│       ├── usage_events.csv
│       └── README.md
│
├── src/
│   ├── command_runner.py
│   ├── csv_ingestion.py
│   ├── usage_ingestion.py
│   ├── usage_aggregation.py
│   ├── rating_engine.py
│   ├── invoice_engine.py
│   ├── database.py
│   └── ...
│
├── tests/
│   └── automated test modules
│
├── output/
│   └── generated CSV reports
│
├── requirements.txt
└── README.md
```

## 8. Input Data

The supplied dataset is stored in `input/T034-Dataset/`.

| File | Purpose |
|---|---|
| `customers.csv` | Customer identity, plan, price book, commitment, and overage settings. |
| `plans.csv` | Monthly quotas, rate limits, and burst allowances for each plan. |
| `metrics.csv` | Metric definitions, aggregation methods, rounding units, and free allowances. |
| `price_books.csv` | Pricing models, tier boundaries, unit rates, and overage multipliers. |
| `usage_events.csv` | Timestamped customer usage events and idempotency keys. |
| `uptime.csv` | Monthly customer uptime percentages used for SLA calculations. |
| `commands.txt` | Ordered instructions for ingestion, invoice generation, and terminal reports. |
| `README.md` | Dataset schema, command format, and documented edge-case scenarios. |

The sample data pack contains 15 customers, 2,853 usage-event records, 30 uptime records, and a command sequence covering September and October 2026. The dataset README describes the included edge cases and input formats.

## 9. System Workflow

The application follows this processing sequence:

1. **Load commands and input data** — read the command file and the customer, plan, metric, price-book, usage-event, and uptime records.
2. **Open the usage month** — initialize the month to be processed.
3. **Ingest events up to the requested cutoff** — process events in the supplied ingestion order.
4. **Validate each event** — check event age, future timestamp, and idempotency.
5. **Apply usage controls** — enforce rate limits, burst allowances, free usage, plan quota, and overage eligibility.
6. **Save event decisions** — record whether each event was metered, partially processed, throttled, blocked, duplicated, or rejected.
7. **Aggregate monthly usage** — calculate API calls, storage, and active users using their configured aggregation methods.
8. **Rate the usage** — apply the relevant price book, tiers, commitment, rollover, and overage rules.
9. **Generate invoices** — apply late adjustments, SLA credits, GST, and invoice rounding.
10. **Print requested reports** — show customer usage, invoice details, and throttle/block decisions in the terminal.

## 10. Command File Format

The command file uses a pipe-delimited format:

```text
COMMAND_NAME|argument1|argument2
```

Commands are processed from top to bottom. Blank lines and lines beginning with `#` are ignored.

| Command | Arguments | Purpose |
|---|---|---|
| `OPEN_MONTH` | `YYYY-MM` | Opens the usage month for event processing. |
| `INGEST_UNTIL` | `YYYY-MM-DD HH:MM:SS` | Processes events ingested before the specified cutoff timestamp. |
| `GENERATE_INVOICES` | `YYYY-MM|run_timestamp` | Generates invoices for the specified month using events available by the invoice run time. |
| `PRINT_USAGE` | `customer_id|YYYY-MM` | Prints the customer's monthly metric usage, including raw, rounded, free, billable, and overage quantities. |
| `PRINT_INVOICE` | `customer_id|YYYY-MM` | Prints the invoice fields for the customer and month. |
| `PRINT_THROTTLE_LOG` | `start_date|end_date` | Prints events that were throttled or blocked in the requested date range. |

The supplied command sequence is already available in `input/T034-Dataset/commands.txt`. It is the default command stream used by the command runner.

## 11. Installation and Setup (Windows PowerShell)

### Step 1 — Clone the repository

```powershell
git clone https://github.com/jashwanth-sariputi/T034-PS-089.git
cd T034-PS-089
```

### Step 2 — Create a virtual environment

```powershell
python -m venv .venv
```

### Step 3 — Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the following command in the current terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Step 4 — Install project dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 12. Run the Application from the Terminal

Make sure the virtual environment is active and the terminal is at the project root.

Run:

```powershell
python -m src.command_runner
```

The command runner automatically reads:

```text
input/T034-Dataset/commands.txt
```

It then executes the commands in the order in which they appear in that file. No separate command-line arguments are required for the supplied sample run.

### What appears in the terminal?

During execution, the terminal displays:

- The PS-089 application heading and command execution start message.
- The usage month opened by each `OPEN_MONTH` command.
- The number of events ingested and the corresponding cutoff timestamp.
- Customer usage reports requested by `PRINT_USAGE`.
- Invoice field values requested by `PRINT_INVOICE`.
- Throttled and blocked event details requested by `PRINT_THROTTLE_LOG`.
- A final message when all commands have completed.

A usage report displays the metric quantities, including raw quantity, rounded quantity, free quantity, billable quantity, and overage quantity. An invoice report prints the generated invoice fields for the selected customer and month.

### Important

Run the command from the repository root. The input files must remain in `input/T034-Dataset/`. The command runner expects the command file and dataset files at those paths.

## 13. Generated Output Reports

The engine writes its generated reports to the `output/` directory.

| Output file | Contents |
|---|---|
| `event_decisions.csv` | Per-event processing decisions, metered quantities, throttled quantities, blocked quantities, overage quantities, and reasons. |
| `usage_summary.csv` | Monthly customer usage by metric, including raw, rounded, free, billable, and overage quantities. |
| `rating_breakdown.csv` | Rated usage and the applicable price-book tier calculations. |
| `invoices.csv` | Monthly invoice totals and components such as usage charges, commitment, overage, adjustments, SLA credits, GST, and rollover. |

These CSV files provide evidence for reviewing the engine's calculations in addition to the terminal reports.

## 14. Run Automated Tests

From the repository root, with the virtual environment activated, run:

```powershell
python -m pytest -v
```

For a concise test summary:

```powershell
python -m pytest -q
```

The test suite is used to verify event processing, validation, rate limiting, quota behavior, usage aggregation, pricing, invoice calculations, commitment handling, SLA credits, and GST. The test result shown in the terminal is the result for the code and test files currently present in the repository.

## 15. Error Handling and Validation

The engine validates event timestamps and applies the configured event-processing rules. It also checks command names and command order. For example, an ingestion command cannot run before a usage month has been opened, and the command runner checks that all dataset events have been processed before completing the run.

If a required input or generated report is missing, or if the command file contains an unsupported command, execution raises an error rather than silently treating the operation as successful.

## 16. Reproducibility

For reproducible execution:

- Use the Python version supported by the project requirements.
- Install dependencies from `requirements.txt`.
- Keep the supplied dataset in `input/T034-Dataset/`.
- Do not change the order of commands in `commands.txt` unless intentionally testing a different scenario.
- Run the command runner from the repository root.
- Run the automated tests after code changes.

## 17. Team

**Team ID:** T034  
**Problem Statement ID:** PS-089  
**Project Title:** API Usage Metering, Tiered Pricing and Overage Engine  
**Language:** Python

## 18. Conclusion

PS-089 provides a terminal-driven workflow for processing API usage events and producing monthly billing results. By combining event validation, idempotency, rate limiting, quota enforcement, metric aggregation, tiered pricing, commitment and overage calculations, SLA credits, and GST, the project demonstrates the core stages of a SaaS API metering and billing engine.

The command file makes the execution sequence reproducible, while terminal reports, CSV outputs, and automated tests support inspection and verification of the processing results.

---

**Repository:** https://github.com/jashwanth-sariputi/T034-PS-089
