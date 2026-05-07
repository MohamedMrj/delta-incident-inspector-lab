from pathlib import Path

from typer.testing import CliRunner

from delta_incident_inspector.cli import app
from scripts.generate_sample_delta_tables import main as generate_sample_delta_tables

runner = CliRunner()


def test_compare_schema_detects_added_email_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    generate_sample_delta_tables()

    result = runner.invoke(
        app,
        [
            "compare-schema",
            "data/delta/customers",
            "--from-version",
            "0",
            "--to-version",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Added" in result.output
    assert "email" in result.output


def test_diff_by_key_detects_duplicate_conflict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    generate_sample_delta_tables()

    result = runner.invoke(
        app,
        [
            "diff-by-key",
            "data/delta/customers",
            "--from-version",
            "2",
            "--to-version",
            "4",
            "--key",
            "customer_id",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Duplicate key conflicts" in result.output
    assert "keys disappeared" in result.output


def test_report_writes_markdown_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    generate_sample_delta_tables()

    output_path = Path("docs/test-incident-report.md")

    result = runner.invoke(
        app,
        [
            "report",
            "data/delta/customers",
            "--from-version",
            "2",
            "--to-version",
            "4",
            "--key",
            "customer_id",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()

    report_text = output_path.read_text(encoding="utf-8")

    assert "# Delta Incident Report" in report_text
    assert "## Key Findings" in report_text
    assert "## Row Count Comparison" in report_text
    assert "## Schema Comparison" in report_text
    assert "## Key-Level Diff" in report_text
    assert "Duplicate key conflicts" in report_text
