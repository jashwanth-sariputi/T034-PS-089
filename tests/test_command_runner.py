import csv

import src.command_runner as runner


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_read_output(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)

    write_csv(
        tmp_path / "sample.csv",
        ["customer_id", "month"],
        [{"customer_id": "API-001", "month": "2026-09"}],
    )

    rows = runner.read_output("sample.csv")

    assert len(rows) == 1
    assert rows[0]["customer_id"] == "API-001"


def test_read_output_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)

    try:
        runner.read_output("missing.csv")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_print_usage(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)

    write_csv(
        tmp_path / "usage_summary.csv",
        [
            "customer_id",
            "month",
            "metric_id",
            "raw_quantity",
            "rounded_quantity",
            "free_quantity",
            "billable_quantity",
            "overage_quantity",
        ],
        [{
            "customer_id": "API-001",
            "month": "2026-09",
            "metric_id": "API_CALLS",
            "raw_quantity": "12000",
            "rounded_quantity": "12000",
            "free_quantity": "10000",
            "billable_quantity": "2000",
            "overage_quantity": "0",
        }],
    )

    runner.print_usage("API-001", "2026-09")

    output = capsys.readouterr().out

    assert "USAGE REPORT: API-001 | 2026-09" in output
    assert "API_CALLS" in output
    assert "billable=2000" in output


def test_print_invoice(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)

    write_csv(
        tmp_path / "invoices.csv",
        ["customer_id", "month", "total_rounded"],
        [{
            "customer_id": "API-001",
            "month": "2026-09",
            "total_rounded": "118.00",
        }],
    )

    runner.print_invoice("API-001", "2026-09")

    output = capsys.readouterr().out

    assert "INVOICE: API-001 | 2026-09" in output
    assert "total_rounded: 118.00" in output


def test_print_throttle_log(tmp_path, monkeypatch, capsys):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(runner, "INPUT", input_dir)
    monkeypatch.setattr(runner, "OUTPUT", output_dir)

    write_csv(
        input_dir / "usage_events.csv",
        ["event_id", "customer_id", "event_ts"],
        [{
            "event_id": "EV-001978",
            "customer_id": "API-013",
            "event_ts": "2026-10-07 11:00:10",
        }],
    )

    write_csv(
        output_dir / "event_decisions.csv",
        [
            "event_id",
            "throttled_quantity",
            "reason",
        ],
        [{
            "event_id": "EV-001978",
            "throttled_quantity": "40",
            "reason": "Rate limit exceeded",
        }],
    )

    runner.print_throttle_log("2026-10-01", "2026-10-31")

    output = capsys.readouterr().out

    assert "EV-001978" in output
    assert "throttled=40" in output
    assert "Throttled events: 1" in output