# PS-089 – API Usage Metering, Tiered Pricing and Overage Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T034.

## Files

| File | What it holds | Row count |
|---|---|---|
| `metrics.csv` | 3 metrics with aggregation, rounding and free allowance | 3 data rows |
| `price_books.csv` | 3 price books: tier type and bands per metric, overage multiplier | 15 data rows |
| `plans.csv` | Quota, rate limit and burst allowance per plan | 3 data rows |
| `customers.csv` | 15 customers: plan, price book, commitment, overage flag, storage use | 15 data rows |
| `usage_events.csv` | Usage events Sep-Oct 2026 in ingestion order, with duplicates, late and future events | 2853 data rows |
| `uptime.csv` | Monthly uptime per customer (SLA credits) | 30 data rows |
| `commands.txt` | Ingestion checkpoints, invoice runs on the 3rd and print requests | 67 command lines (excluding comments) |

Volumes in this sample are reduced for email delivery; the hidden evaluation set is larger and uses the same schema.

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and only occurs in columns whose notes say so.

### `metrics.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| metric_id | string | — | API_CALLS, STORAGE_GB, ACTIVE_USERS | — |
| metric_name | string | — | — | — |
| unit | string | — | — | — |
| aggregation | enum | — | SUM, MAX_HOURLY_AVG_MONTH, UNIQUE_MONTH | storage: max per UTC hour, averaged over every hour of the month |
| rounding_unit | decimal | — | 1, 0.01 | monthly quantity rounded UP to this |
| free_allowance_per_month | decimal | — | — | deducted before tiering; free calls do not count toward quota |

### `price_books.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| price_book_id | string | — | PB-VOLUME, PB-GRADUATED, PB-ENTERPRISE | — |
| metric_id | string | — | metrics.csv | — |
| tier_type | enum | — | VOLUME, GRADUATED, FLAT | VOLUME: all billable units at the band reached; GRADUATED: each band priced separately |
| tier_from | int | billable units | — | inclusive |
| tier_to | int | billable units | — | inclusive; empty = no upper bound |
| unit_price | decimal | Rs | — | 3 decimals |
| overage_multiplier | decimal | — | 1.50 | on the top band row only: overage rate = top rate x this |

### `plans.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| plan_id | enum | — | STARTER, GROWTH, SCALE | — |
| monthly_call_quota | int | calls | — | counted after the 10,000 free calls |
| rate_limit_calls_per_60s | int | — | 600 | rolling window (t - 60 s, t] on event_ts |
| burst_calls_per_hour | int | — | 100 | extra calls above 600, one pool per customer per UTC clock hour |

### `customers.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| customer_id | string | API-nnn | — | — |
| company_name | string | — | — | — |
| state | string | — | — | GST: CGST+SGST if Karnataka, else IGST (18% total) |
| gstin | string | — | — | may be empty |
| plan_id | string | — | plans.csv | — |
| price_book_id | string | — | price_books.csv | — |
| monthly_commitment | decimal | Rs | — | 0.00 = none; else 15% discount and minimum |
| overage_enabled | bool | — | — | false: calls beyond quota are BLOCKED |
| uses_storage | bool | — | — | true if the customer sends STORAGE_GB samples |

### `usage_events.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| event_id | string | EV-nnnnnn | — | row id |
| idempotency_key | string | — | — | same key within 24 h of the first ingestion = duplicate |
| customer_id | string | — | customers.csv | — |
| metric_id | string | — | metrics.csv | — |
| event_ts | timestamp | UTC | — | usage instant; decides the month |
| ingested_ts | timestamp | UTC | — | file is sorted by this |
| quantity | decimal | — | — | calls (int) / GB (2 decimals) / 1 per user event |
| user_id | string | — | — | ACTIVE_USERS only |

### `uptime.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| customer_id | string | — | customers.csv | — |
| month | string | YYYY-MM | — | — |
| uptime_pct | decimal | % | — | 3 decimals |
| source | string | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two pipes in a row) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `OPEN_MONTH` | `YYYY-MM` | Start metering a calendar month (UTC) |
| `INGEST_UNTIL` | `timestamp` | Process every event with ingested_ts before this instant (dedupe, late/future checks, rate limit, quota) |
| `GENERATE_INVOICES` | `YYYY-MM|run_ts` | Rate the month for every customer and issue invoices (late events after run_ts go to the next invoice as adjustments) |
| `PRINT_USAGE` | `customer_id|YYYY-MM` | Usage summary per metric |
| `PRINT_INVOICE` | `customer_id|YYYY-MM` | Invoice with rating breakdown |
| `PRINT_THROTTLE_LOG` | `from_date|to_date` | THROTTLED / BLOCKED decisions |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Usage of exactly 1,00,000 calls under volume tiering vs 1,00,001**
  - API-010 (GROWTH, PB-VOLUME): September calls = 1,10,000 -> after the 10,000 free calls exactly 1,00,000 billable -> whole usage at Rs 0.10 = Rs 10,000.00. API-004: 1,10,001 calls -> 1,00,001 billable -> whole usage at Rs 0.08 = Rs 8,000.08 (volume tiering). Neither customer is throttled, duplicated or late — `customers.csv API-010 (row 10); customers.csv API-004 (row 4); usage_events.csv rows 12-1698 (V100 call events)`
- **EC-02 Duplicate idempotency key arriving 24 hours and 1 second after the original**
  - EV-001177: key 005A000017 re-sent 24 h + 1 s after the original ingestion -> outside the 24-hour window -> NOT a duplicate, metered again; contrast key 005A000018 re-sent after 23:59:59 -> duplicate, ignored — `usage_events.csv EV-001177 (row 1177); usage_events.csv EV-001241 (row 1241) (re-send, counted); usage_events.csv EV-001356 (row 1356); usage_events.csv EV-001409 (row 1409) (re-send, ignored)`
- **EC-03 Event at 23:59:59 UTC on the last day of the month ingested on the 2nd**
  - EV-001785: event_ts 2026-09-30 23:59:59 ingested 2026-10-02 09:12:05 -> September usage, included in the September invoice generated on 2026-10-03; contrast EV-001815: event 2026-09-30 22:10:00 ingested 2026-10-03 06:30:00 (after the invoice run, inside 72 h) -> adjustment line on the October invoice — `usage_events.csv EV-001785 (row 1785); usage_events.csv EV-001815 (row 1815); commands.txt line 5`
- **EC-04 Burst allowance used at 10:59:59 and again at 11:00:00**
  - API-013 on 2026-10-07: 600 calls between 10:59:30 and 10:59:50 fill the 60-second window; 50 more at 10:59:59 use the hour-10 burst allowance; 80 at 11:00:00 (window still holds 650) use the hour-11 burst (burst is once per clock hour); of 60 at 11:00:10 only the remaining 20 burst calls pass and 40 are THROTTLED (not metered) — `customers.csv API-013 (row 13); usage_events.csv EV-001971 (row 1971); usage_events.csv EV-001976 (row 1976); usage_events.csv EV-001977 (row 1977); usage_events.csv EV-001978 (row 1978)`
- **EC-05 Commitment shortfall rollover when next month has no overage**
  - API-002 (commitment Rs 50,000, graduated): September usage rates below the commitment after the 15% discount -> Rs 50,000 invoiced and the shortfall rolls over one month; October has no overage (well inside the GROWTH quota) -> the rollover is not used and lapses — `customers.csv API-002 (row 2)`
- **EC-06 Uptime exactly 99.9 percent - no credit**
  - API-010: September uptime exactly 99.900% -> not below 99.9 -> no SLA credit; contrast API-004: 99.899% -> 10% credit on the October invoice — `uptime.csv API-010 (row 19); customers.csv API-010 (row 10); uptime.csv API-004 (row 7); customers.csv API-004 (row 4)`
- **EC-07 SLA credit larger than next month's base charge**
  - API-008: September uptime 94.500% -> 50% of the September base charge as credit; its October usage is small (1,499 billable calls, no storage, at most 8 users) -> the credit is capped at October's base charge, the excess is forfeited (never paid as cash) — `uptime.csv API-008 (row 15); customers.csv API-008 (row 8)`
- **EC-08 Storage sample missing for 6 hours - treat missing hours as the last known value**
  - API-014: hourly storage samples for 2026-09-17 13:00 .. 18:59 are missing (6 hours) -> each missing hour takes the last known value, the 12:00 sample 156.84 GB — `customers.csv API-014 (row 14); usage_events.csv EV-000956 (row 956) (last sample before the gap)`
- **Extra traps (not in the brief, but realistic):**
  - API-011 (STARTER, overage disabled): September calls 1,12,000 -> 10,000 free + 1,00,000 quota; the last 2,000 calls are BLOCKED (not metered) — `customers.csv API-011 (row 11)`
  - EV-002159: event_ts 2026-10-09 08:00:00 ingested 2026-10-12 08:00:01 -> 72 h + 1 s -> REJECTED LATE — `usage_events.csv EV-002159 (row 2159)`
  - EV-002273: event_ts 5 min 1 s after its ingestion time -> REJECTED (future); EV-002274 exactly 5 min ahead -> accepted — `usage_events.csv EV-002273 (row 2273); usage_events.csv EV-002274 (row 2274)`
  - API-001: GROWTH customer with overage enabled — in this reduced sample its usage stays inside the quota; the hidden set contains a real overage month (10,000 free + 10,00,000 quota + 2,000) for the same configuration — `customers.csv API-001 (row 1)`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `event_decisions.csv`

One row per usage_events.csv row, in file order.

Columns, in order: `event_id`, `decision`, `metered_quantity`, `throttled_quantity`, `blocked_quantity`, `overage_quantity`, `reason`

### `usage_summary.csv`

One row per customer per month per metric.

Columns, in order: `customer_id`, `month`, `metric_id`, `raw_quantity`, `rounded_quantity`, `free_quantity`, `billable_quantity`, `overage_quantity`

### `rating_breakdown.csv`

One row per customer, month, metric and band.

Columns, in order: `customer_id`, `month`, `metric_id`, `tier_type`, `band_from`, `band_to`, `quantity`, `unit_price`, `amount`

### `invoices.csv`

One row per customer per month.

Columns, in order: `customer_id`, `month`, `usage_charge`, `commitment_discount`, `commitment_topup`, `base_charge`, `overage_charge`, `adjustments`, `sla_credit`, `net`, `gst`, `total_rounded`, `rollover_created`, `rollover_used`

Binding choices where the brief is silent: duplicates are judged on ingested_ts (<= 24:00:00 after the first ingestion of that key); LATE = event_ts more than 72:00:00 before ingested_ts; FUTURE = event_ts more than 00:05:00 after ingested_ts. Rate limiting runs in ingestion order on event_ts, call by call; a partly allowed event is split into metered and throttled quantities. base_charge = max(usage_charge x 0.85, commitment) for committed customers, else usage_charge (all metrics, excluding overage). SLA credit percentages are of the month's base_charge and are applied on the next month's invoice, capped at that invoice's base_charge (excess forfeited). Minimum invoice Rs 100 after credits (raised to 100). Money 2 decimals; total rounded to the rupee.
