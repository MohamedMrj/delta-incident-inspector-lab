from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Optional

import pyarrow as pa
import typer
from deltalake import DeltaTable
from rich.console import Console
from rich.table import Table

from delta_incident_inspector.key_diff import diff_by_key_dataframes
from delta_incident_inspector.reports import build_markdown_report
from delta_incident_inspector.row_counts import compare_row_counts as compare_table_row_counts
from delta_incident_inspector.schema_compare import compare_schemas

app = typer.Typer(
    help="Delta Incident Inspector: investigate Delta table history, schemas, and row counts."
)

console = Console()


@app.command()
def version() -> None:
    """Show the tool version."""
    console.print("Delta Incident Inspector v0.1.0")


@app.command()
def doctor() -> None:
    """Check whether the local project environment is ready."""
    console.print("[bold]Environment check[/bold]")

    checks = Table(title="Doctor")
    checks.add_column("Check")
    checks.add_column("Result")

    checks.add_row("Python", platform.python_version())
    checks.add_row("Platform", platform.platform())
    checks.add_row("PyArrow", pa.__version__)

    data_dir = Path("data")
    checks.add_row("Data directory exists", "yes" if data_dir.exists() else "no")

    try:
        import deltalake

        checks.add_row("deltalake package", deltalake.__version__)
    except Exception as exc:
        checks.add_row("deltalake package", f"failed: {exc}")

    console.print(checks)


@app.command()
def history(table_path: Path) -> None:
    """Show Delta table history."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    delta_table = DeltaTable(str(table_path))
    history_rows = delta_table.history()

    table = Table(title=f"Delta history: {table_path}")
    table.add_column("Version")
    table.add_column("Timestamp")
    table.add_column("Operation")

    for row in history_rows:
        table.add_row(
            str(row.get("version", "")),
            str(row.get("timestamp", "")),
            str(row.get("operation", "")),
        )

    console.print(table)


@app.command("row-count")
def row_count(table_path: Path, version: Optional[int] = None) -> None:
    """Show row count for a Delta table version."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    delta_table = DeltaTable(str(table_path), version=version)
    arrow_table = delta_table.to_pyarrow_table()

    actual_version = delta_table.version()

    console.print(
        f"[bold]Table:[/bold] {table_path}\n"
        f"[bold]Version:[/bold] {actual_version}\n"
        f"[bold]Rows:[/bold] {arrow_table.num_rows}"
    )


@app.command("compare-row-counts")
def compare_row_counts(
    table_path: Path,
    from_version: int = typer.Option(..., "--from-version"),
    to_version: int = typer.Option(..., "--to-version"),
    warning_threshold_percent: float = typer.Option(
        50.0,
        "--warning-threshold-percent",
        help="Warn when row count drops by this percentage or more.",
    ),
) -> None:
    """Compare row counts between two Delta table versions."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    comparison = compare_table_row_counts(
        table_path=table_path,
        from_version=from_version,
        to_version=to_version,
    )

    table = Table(title=f"Row count comparison: v{from_version} → v{to_version}")
    table.add_column("Metric")
    table.add_column("Value")

    table.add_row("Table", str(comparison.table_path))
    table.add_row("From version", str(comparison.from_version))
    table.add_row("From row count", str(comparison.from_rows))
    table.add_row("To version", str(comparison.to_version))
    table.add_row("To row count", str(comparison.to_rows))
    table.add_row("Difference", str(comparison.difference))
    table.add_row("Percent change", comparison.percent_change_text)

    console.print(table)

    if comparison.is_suspicious_drop(warning_threshold_percent):
        console.print(
            f"[bold red]Warning:[/bold red] suspicious row count drop detected "
            f"({comparison.percent_change_text})."
        )
    elif comparison.difference < 0:
        console.print(
            f"[yellow]Notice:[/yellow] row count decreased by {abs(comparison.difference)} rows."
        )
    elif comparison.difference > 0:
        console.print(
            f"[green]Notice:[/green] row count increased by {comparison.difference} rows."
        )
    else:
        console.print("[green]No row count change detected.[/green]")


@app.command("schema")
def schema(table_path: Path, version: Optional[int] = None) -> None:
    """Print the schema for a Delta table version."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    delta_table = DeltaTable(str(table_path), version=version)
    schema_obj = delta_table.schema()

    if hasattr(schema_obj, "to_json"):
        schema_json = json.loads(schema_obj.to_json())
    else:
        schema_raw = schema_obj.json()
        schema_json = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw

    table = Table(title=f"Schema: {table_path} | version {delta_table.version()}")
    table.add_column("Column")
    table.add_column("Type")
    table.add_column("Nullable")

    for field in schema_json["fields"]:
        table.add_row(
            field["name"],
            json.dumps(field["type"]),
            str(field["nullable"]),
        )

    console.print(table)


@app.command("compare-schema")
def compare_schema(
    table_path: Path,
    from_version: int = typer.Option(..., "--from-version"),
    to_version: int = typer.Option(..., "--to-version"),
) -> None:
    """Compare schema between two Delta table versions."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    from_table = DeltaTable(str(table_path), version=from_version)
    to_table = DeltaTable(str(table_path), version=to_version)

    comparison = compare_schemas(from_table=from_table, to_table=to_table)

    table = Table(title=f"Schema comparison: v{from_version} → v{to_version}")
    table.add_column("Change Type")
    table.add_column("Column")
    table.add_column("Details")

    for column in comparison.added:
        table.add_row("Added", column, str(comparison.to_fields[column]))

    for column in comparison.removed:
        table.add_row("Removed", column, str(comparison.from_fields[column]))

    for column in comparison.changed:
        table.add_row(
            "Changed",
            column,
            f"{comparison.from_fields[column]} -> {comparison.to_fields[column]}",
        )

    if not comparison.has_changes:
        table.add_row("No change", "-", "-")

    console.print(table)


@app.command("diff-by-key")
def diff_by_key(
    table_path: Path,
    from_version: int = typer.Option(..., "--from-version"),
    to_version: int = typer.Option(..., "--to-version"),
    key: str = typer.Option(..., "--key"),
    max_examples: int = typer.Option(
        20,
        "--max-examples",
        help="Maximum number of example keys to display per category.",
    ),
) -> None:
    """Compare two Delta table versions by business key."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    from_table = DeltaTable(str(table_path), version=from_version)
    to_table = DeltaTable(str(table_path), version=to_version)

    from_df = from_table.to_pyarrow_table().to_pandas()
    to_df = to_table.to_pyarrow_table().to_pandas()

    key_summary = _diff_by_key_for_report(
        from_df=from_df,
        to_df=to_df,
        key=key,
        max_examples=max_examples,
    )

    summary = Table(title=f"Key diff: v{from_version} → v{to_version} by '{key}'")
    summary.add_column("Metric")
    summary.add_column("Value")

    summary.add_row("Table", str(table_path))
    summary.add_row("From version", str(from_version))
    summary.add_row("From rows", str(len(from_df)))
    summary.add_row("From distinct non-null keys", str(key_summary["from_distinct_keys"]))
    summary.add_row("From null key rows", str(key_summary["from_null_key_rows"]))
    summary.add_row("To version", str(to_version))
    summary.add_row("To rows", str(len(to_df)))
    summary.add_row("To distinct non-null keys", str(key_summary["to_distinct_keys"]))
    summary.add_row("To null key rows", str(key_summary["to_null_key_rows"]))
    summary.add_row("Inserted keys", str(len(key_summary["inserted"])))
    summary.add_row("Deleted keys", str(len(key_summary["deleted"])))
    summary.add_row("Changed comparable keys", str(len(key_summary["changed"])))
    summary.add_row("Unchanged comparable keys", str(len(key_summary["unchanged"])))
    summary.add_row("Duplicate key conflicts", str(len(key_summary["duplicate_conflicts"])))

    console.print(summary)

    examples = Table(title="Example keys")
    examples.add_column("Category")
    examples.add_column("Examples")

    examples.add_row("Inserted", _format_list(key_summary["inserted_examples"]))
    examples.add_row("Deleted", _format_list(key_summary["deleted_examples"]))
    examples.add_row("Changed", _format_list(key_summary["changed_examples"]))
    examples.add_row("Duplicate conflicts", _format_list(key_summary["duplicate_examples"]))

    console.print(examples)

    if key_summary["duplicate_conflicts"]:
        console.print(
            "[bold red]Warning:[/bold red] duplicate keys detected. "
            "Changed/unchanged comparison excludes duplicated keys because one-to-one comparison is unsafe."
        )

    if key_summary["deleted"]:
        console.print(
            "[yellow]Notice:[/yellow] keys disappeared between versions. "
            "This may indicate filtering, overwrite, deletion, or data loss."
        )

    if key_summary["inserted"]:
        console.print("[green]Notice:[/green] new keys appeared in the target version.")

    if key_summary["changed"]:
        console.print("[yellow]Notice:[/yellow] existing keys changed values between versions.")


@app.command("report")
def report(
    table_path: Path,
    from_version: int = typer.Option(..., "--from-version"),
    to_version: int = typer.Option(..., "--to-version"),
    key: Optional[str] = typer.Option(
        None,
        "--key",
        help="Optional business key column used for key-level diff summary.",
    ),
    output: Path = typer.Option(
        Path("docs/incident-report.md"),
        "--output",
        help="Path where the Markdown report should be written.",
    ),
    generated_at: Optional[str] = typer.Option(
        None,
        "--generated-at",
        help="Optional fixed timestamp for deterministic report generation.",
    ),
) -> None:
    """Generate a Markdown incident report comparing two Delta table versions."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    row_count_comparison = compare_table_row_counts(
        table_path=table_path,
        from_version=from_version,
        to_version=to_version,
    )

    from_table = DeltaTable(str(table_path), version=from_version)
    to_table = DeltaTable(str(table_path), version=to_version)

    from_df = from_table.to_pyarrow_table().to_pandas()
    to_df = to_table.to_pyarrow_table().to_pandas()

    schema_summary = _compare_schemas_for_report(from_table, to_table)

    key_summary = None
    if key is not None:
        key_summary = _diff_by_key_for_report(
            from_df=from_df,
            to_df=to_df,
            key=key,
            max_examples=20,
        )

    findings = []

    if row_count_comparison.is_suspicious_drop(warning_threshold_percent=50.0):
        findings.append(
            "Suspicious row count drop detected: "
            f"{row_count_comparison.from_rows} → {row_count_comparison.to_rows} "
            f"({row_count_comparison.percent_change_text})."
        )
    elif row_count_comparison.difference < 0:
        findings.append(f"Row count decreased by {abs(row_count_comparison.difference)} rows.")

    if schema_summary["added"]:
        findings.append("Schema columns were added: " + ", ".join(schema_summary["added"]) + ".")

    if schema_summary["removed"]:
        findings.append(
            "Schema columns were removed: " + ", ".join(schema_summary["removed"]) + "."
        )

    if schema_summary["changed"]:
        findings.append(
            "Schema columns changed type/nullability: " + ", ".join(schema_summary["changed"]) + "."
        )

    if key_summary is not None:
        if key_summary["duplicate_conflicts"]:
            findings.append(
                f"Duplicate key conflicts detected for '{key}'. "
                "One-to-one record comparison is unsafe for those keys."
            )

        if key_summary["deleted"]:
            findings.append(f"{len(key_summary['deleted'])} key(s) disappeared between versions.")

        if key_summary["changed"]:
            findings.append(f"{len(key_summary['changed'])} comparable key(s) changed values.")

    if not findings:
        findings.append("No obvious suspicious changes detected by the current checks.")

    output.parent.mkdir(parents=True, exist_ok=True)

    report_markdown = build_markdown_report(
        table_path=table_path,
        from_version=from_version,
        to_version=to_version,
        from_rows=row_count_comparison.from_rows,
        to_rows=row_count_comparison.to_rows,
        row_difference=row_count_comparison.difference,
        percent_change_text=row_count_comparison.percent_change_text,
        schema_summary=schema_summary,
        key=key,
        key_summary=key_summary,
        findings=findings,
        generated_at=generated_at,
    )

    output.write_text(report_markdown, encoding="utf-8")

    console.print(f"[green]Report written to:[/green] {output}")


def _compare_schemas_for_report(from_table: DeltaTable, to_table: DeltaTable) -> dict:
    comparison = compare_schemas(from_table=from_table, to_table=to_table)

    return {
        "added": comparison.added,
        "removed": comparison.removed,
        "changed": comparison.changed,
        "from_fields": comparison.from_fields,
        "to_fields": comparison.to_fields,
    }


def _diff_by_key_for_report(from_df, to_df, key: str, max_examples: int) -> dict:
    try:
        summary = diff_by_key_dataframes(
            from_df=from_df,
            to_df=to_df,
            key=key,
            max_examples=max_examples,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    return summary.to_dict()


def _format_list(values: list) -> str:
    if not values:
        return "-"

    return ", ".join(str(value) for value in values)
