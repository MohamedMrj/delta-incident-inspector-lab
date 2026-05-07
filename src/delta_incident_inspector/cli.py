from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pyarrow as pa
import typer
from deltalake import DeltaTable
from rich.console import Console
from rich.table import Table

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

    from_table = DeltaTable(str(table_path), version=from_version)
    to_table = DeltaTable(str(table_path), version=to_version)

    from_rows = from_table.to_pyarrow_table().num_rows
    to_rows = to_table.to_pyarrow_table().num_rows

    difference = to_rows - from_rows

    if from_rows == 0:
        percent_change_text = "n/a"
        percent_change_value = None
    else:
        percent_change_value = (difference / from_rows) * 100
        percent_change_text = f"{percent_change_value:.2f}%"

    table = Table(title=f"Row count comparison: v{from_version} → v{to_version}")
    table.add_column("Metric")
    table.add_column("Value")

    table.add_row("Table", str(table_path))
    table.add_row("From version", str(from_version))
    table.add_row("From row count", str(from_rows))
    table.add_row("To version", str(to_version))
    table.add_row("To row count", str(to_rows))
    table.add_row("Difference", str(difference))
    table.add_row("Percent change", percent_change_text)

    console.print(table)

    if percent_change_value is not None and percent_change_value <= -warning_threshold_percent:
        console.print(
            f"[bold red]Warning:[/bold red] suspicious row count drop detected "
            f"({percent_change_text})."
        )
    elif difference < 0:
        console.print(
            f"[yellow]Notice:[/yellow] row count decreased by {abs(difference)} rows."
        )
    elif difference > 0:
        console.print(
            f"[green]Notice:[/green] row count increased by {difference} rows."
        )
    else:
        console.print("[green]No row count change detected.[/green]")


@app.command("schema")
def schema(table_path: Path, version: Optional[int] = None) -> None:
    """Print the schema for a Delta table version."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    delta_table = DeltaTable(str(table_path), version=version)
    schema_json = delta_table.schema().json()

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

    from_schema = from_table.schema().json()
    to_schema = to_table.schema().json()

    from_fields = {
        field["name"]: {
            "type": json.dumps(field["type"]),
            "nullable": field["nullable"],
        }
        for field in from_schema["fields"]
    }

    to_fields = {
        field["name"]: {
            "type": json.dumps(field["type"]),
            "nullable": field["nullable"],
        }
        for field in to_schema["fields"]
    }

    added = sorted(set(to_fields) - set(from_fields))
    removed = sorted(set(from_fields) - set(to_fields))

    changed = []
    for column in sorted(set(from_fields) & set(to_fields)):
        if from_fields[column] != to_fields[column]:
            changed.append(column)

    table = Table(title=f"Schema comparison: v{from_version} → v{to_version}")
    table.add_column("Change Type")
    table.add_column("Column")
    table.add_column("Details")

    for column in added:
        table.add_row("Added", column, str(to_fields[column]))

    for column in removed:
        table.add_row("Removed", column, str(from_fields[column]))

    for column in changed:
        table.add_row(
            "Changed",
            column,
            f"{from_fields[column]} -> {to_fields[column]}",
        )

    if not added and not removed and not changed:
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

    if key not in from_df.columns:
        raise typer.BadParameter(f"Key column '{key}' does not exist in version {from_version}")

    if key not in to_df.columns:
        raise typer.BadParameter(f"Key column '{key}' does not exist in version {to_version}")

    from_null_key_rows = int(from_df[key].isna().sum())
    to_null_key_rows = int(to_df[key].isna().sum())

    from_non_null = from_df[from_df[key].notna()].copy()
    to_non_null = to_df[to_df[key].notna()].copy()

    from_key_counts = from_non_null[key].value_counts()
    to_key_counts = to_non_null[key].value_counts()

    from_keys = set(from_key_counts.index.tolist())
    to_keys = set(to_key_counts.index.tolist())

    from_duplicate_keys = set(from_key_counts[from_key_counts > 1].index.tolist())
    to_duplicate_keys = set(to_key_counts[to_key_counts > 1].index.tolist())

    inserted_keys = sorted(to_keys - from_keys, key=str)
    deleted_keys = sorted(from_keys - to_keys, key=str)

    duplicate_conflict_keys = sorted(from_duplicate_keys | to_duplicate_keys, key=str)

    common_keys = from_keys & to_keys
    comparable_keys = sorted(
        common_keys - from_duplicate_keys - to_duplicate_keys,
        key=str,
    )

    value_columns = sorted((set(from_df.columns) | set(to_df.columns)) - {key})

    def align_values(df, columns):
        aligned = df.copy()

        for column in columns:
            if column not in aligned.columns:
                aligned[column] = None

        return aligned[columns].astype("string").fillna("<NULL>")

    from_unique = (
        from_non_null[from_non_null[key].isin(comparable_keys)]
        .drop_duplicates(subset=[key])
        .set_index(key)
    )

    to_unique = (
        to_non_null[to_non_null[key].isin(comparable_keys)]
        .drop_duplicates(subset=[key])
        .set_index(key)
    )

    from_values = align_values(from_unique, value_columns).reindex(comparable_keys)
    to_values = align_values(to_unique, value_columns).reindex(comparable_keys)

    changed_keys = []
    unchanged_keys = []

    for key_value in comparable_keys:
        if from_values.loc[key_value].equals(to_values.loc[key_value]):
            unchanged_keys.append(key_value)
        else:
            changed_keys.append(key_value)

    summary = Table(title=f"Key diff: v{from_version} → v{to_version} by '{key}'")
    summary.add_column("Metric")
    summary.add_column("Value")

    summary.add_row("Table", str(table_path))
    summary.add_row("From version", str(from_version))
    summary.add_row("From rows", str(len(from_df)))
    summary.add_row("From distinct non-null keys", str(len(from_keys)))
    summary.add_row("From null key rows", str(from_null_key_rows))
    summary.add_row("To version", str(to_version))
    summary.add_row("To rows", str(len(to_df)))
    summary.add_row("To distinct non-null keys", str(len(to_keys)))
    summary.add_row("To null key rows", str(to_null_key_rows))
    summary.add_row("Inserted keys", str(len(inserted_keys)))
    summary.add_row("Deleted keys", str(len(deleted_keys)))
    summary.add_row("Changed comparable keys", str(len(changed_keys)))
    summary.add_row("Unchanged comparable keys", str(len(unchanged_keys)))
    summary.add_row("Duplicate key conflicts", str(len(duplicate_conflict_keys)))

    console.print(summary)

    def format_examples(values) -> str:
        if not values:
            return "-"

        shown = values[:max_examples]
        suffix = "" if len(values) <= max_examples else f" ... +{len(values) - max_examples} more"
        return ", ".join(str(value) for value in shown) + suffix

    examples = Table(title="Example keys")
    examples.add_column("Category")
    examples.add_column("Examples")

    examples.add_row("Inserted", format_examples(inserted_keys))
    examples.add_row("Deleted", format_examples(deleted_keys))
    examples.add_row("Changed", format_examples(changed_keys))
    examples.add_row("Duplicate conflicts", format_examples(duplicate_conflict_keys))

    console.print(examples)

    if duplicate_conflict_keys:
        console.print(
            "[bold red]Warning:[/bold red] duplicate keys detected. "
            "Changed/unchanged comparison excludes duplicated keys because one-to-one comparison is unsafe."
        )

    if deleted_keys:
        console.print(
            "[yellow]Notice:[/yellow] keys disappeared between versions. "
            "This may indicate filtering, overwrite, deletion, or data loss."
        )

    if inserted_keys:
        console.print("[green]Notice:[/green] new keys appeared in the target version.")

    if changed_keys:
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
) -> None:
    """Generate a Markdown incident report comparing two Delta table versions."""
    if not table_path.exists():
        raise typer.BadParameter(f"Table path does not exist: {table_path}")

    from_table = DeltaTable(str(table_path), version=from_version)
    to_table = DeltaTable(str(table_path), version=to_version)

    from_df = from_table.to_pyarrow_table().to_pandas()
    to_df = to_table.to_pyarrow_table().to_pandas()

    from_rows = len(from_df)
    to_rows = len(to_df)
    row_difference = to_rows - from_rows

    if from_rows == 0:
        percent_change = None
        percent_change_text = "n/a"
    else:
        percent_change = (row_difference / from_rows) * 100
        percent_change_text = f"{percent_change:.2f}%"

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

    if percent_change is not None and percent_change <= -50:
        findings.append(
            f"Suspicious row count drop detected: {from_rows} → {to_rows} ({percent_change_text})."
        )
    elif row_difference < 0:
        findings.append(f"Row count decreased by {abs(row_difference)} rows.")

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

    report_markdown = _build_markdown_report(
        table_path=table_path,
        from_version=from_version,
        to_version=to_version,
        from_rows=from_rows,
        to_rows=to_rows,
        row_difference=row_difference,
        percent_change_text=percent_change_text,
        schema_summary=schema_summary,
        key=key,
        key_summary=key_summary,
        findings=findings,
    )

    output.write_text(report_markdown, encoding="utf-8")

    console.print(f"[green]Report written to:[/green] {output}")


def _compare_schemas_for_report(from_table: DeltaTable, to_table: DeltaTable) -> dict:
    from_schema = from_table.schema().json()
    to_schema = to_table.schema().json()

    from_fields = {
        field["name"]: {
            "type": json.dumps(field["type"]),
            "nullable": field["nullable"],
        }
        for field in from_schema["fields"]
    }

    to_fields = {
        field["name"]: {
            "type": json.dumps(field["type"]),
            "nullable": field["nullable"],
        }
        for field in to_schema["fields"]
    }

    added = sorted(set(to_fields) - set(from_fields))
    removed = sorted(set(from_fields) - set(to_fields))

    changed = []
    for column in sorted(set(from_fields) & set(to_fields)):
        if from_fields[column] != to_fields[column]:
            changed.append(column)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "from_fields": from_fields,
        "to_fields": to_fields,
    }


def _diff_by_key_for_report(from_df, to_df, key: str, max_examples: int) -> dict:
    if key not in from_df.columns:
        raise typer.BadParameter(f"Key column '{key}' does not exist in from-version data")

    if key not in to_df.columns:
        raise typer.BadParameter(f"Key column '{key}' does not exist in to-version data")

    from_null_key_rows = int(from_df[key].isna().sum())
    to_null_key_rows = int(to_df[key].isna().sum())

    from_non_null = from_df[from_df[key].notna()].copy()
    to_non_null = to_df[to_df[key].notna()].copy()

    from_key_counts = from_non_null[key].value_counts()
    to_key_counts = to_non_null[key].value_counts()

    from_keys = set(from_key_counts.index.tolist())
    to_keys = set(to_key_counts.index.tolist())

    from_duplicate_keys = set(from_key_counts[from_key_counts > 1].index.tolist())
    to_duplicate_keys = set(to_key_counts[to_key_counts > 1].index.tolist())

    inserted = sorted(to_keys - from_keys, key=str)
    deleted = sorted(from_keys - to_keys, key=str)
    duplicate_conflicts = sorted(from_duplicate_keys | to_duplicate_keys, key=str)

    common_keys = from_keys & to_keys
    comparable_keys = sorted(
        common_keys - from_duplicate_keys - to_duplicate_keys,
        key=str,
    )

    value_columns = sorted((set(from_df.columns) | set(to_df.columns)) - {key})

    def align_values(df, columns):
        aligned = df.copy()

        for column in columns:
            if column not in aligned.columns:
                aligned[column] = None

        return aligned[columns].astype("string").fillna("<NULL>")

    from_unique = (
        from_non_null[from_non_null[key].isin(comparable_keys)]
        .drop_duplicates(subset=[key])
        .set_index(key)
    )

    to_unique = (
        to_non_null[to_non_null[key].isin(comparable_keys)]
        .drop_duplicates(subset=[key])
        .set_index(key)
    )

    from_values = align_values(from_unique, value_columns).reindex(comparable_keys)
    to_values = align_values(to_unique, value_columns).reindex(comparable_keys)

    changed = []
    unchanged = []

    for key_value in comparable_keys:
        if from_values.loc[key_value].equals(to_values.loc[key_value]):
            unchanged.append(key_value)
        else:
            changed.append(key_value)

    return {
        "from_null_key_rows": from_null_key_rows,
        "to_null_key_rows": to_null_key_rows,
        "from_distinct_keys": len(from_keys),
        "to_distinct_keys": len(to_keys),
        "inserted": inserted,
        "deleted": deleted,
        "changed": changed,
        "unchanged": unchanged,
        "duplicate_conflicts": duplicate_conflicts,
        "inserted_examples": inserted[:max_examples],
        "deleted_examples": deleted[:max_examples],
        "changed_examples": changed[:max_examples],
        "duplicate_examples": duplicate_conflicts[:max_examples],
    }


def _format_list(values: list) -> str:
    if not values:
        return "-"

    return ", ".join(str(value) for value in values)


def _build_markdown_report(
    table_path: Path,
    from_version: int,
    to_version: int,
    from_rows: int,
    to_rows: int,
    row_difference: int,
    percent_change_text: str,
    schema_summary: dict,
    key: Optional[str],
    key_summary: Optional[dict],
    findings: list[str],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Delta Incident Report",
        "",
        "## Summary",
        "",
        f"- **Generated at:** `{generated_at}`",
        f"- **Table path:** `{table_path}`",
        f"- **Compared versions:** `{from_version}` → `{to_version}`",
        "",
        "## Key Findings",
        "",
    ]

    for finding in findings:
        lines.append(f"- {finding}")

    lines.extend(
        [
            "",
            "## Row Count Comparison",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| From version | {from_version} |",
            f"| From row count | {from_rows} |",
            f"| To version | {to_version} |",
            f"| To row count | {to_rows} |",
            f"| Difference | {row_difference} |",
            f"| Percent change | {percent_change_text} |",
            "",
            "## Schema Comparison",
            "",
            "| Change Type | Columns |",
            "|---|---|",
            f"| Added | {_format_list(schema_summary['added'])} |",
            f"| Removed | {_format_list(schema_summary['removed'])} |",
            f"| Changed | {_format_list(schema_summary['changed'])} |",
            "",
        ]
    )

    if key_summary is not None and key is not None:
        lines.extend(
            [
                "## Key-Level Diff",
                "",
                f"- **Key column:** `{key}`",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| From distinct non-null keys | {key_summary['from_distinct_keys']} |",
                f"| To distinct non-null keys | {key_summary['to_distinct_keys']} |",
                f"| From null key rows | {key_summary['from_null_key_rows']} |",
                f"| To null key rows | {key_summary['to_null_key_rows']} |",
                f"| Inserted keys | {len(key_summary['inserted'])} |",
                f"| Deleted keys | {len(key_summary['deleted'])} |",
                f"| Changed comparable keys | {len(key_summary['changed'])} |",
                f"| Unchanged comparable keys | {len(key_summary['unchanged'])} |",
                f"| Duplicate key conflicts | {len(key_summary['duplicate_conflicts'])} |",
                "",
                "### Example Keys",
                "",
                "| Category | Examples |",
                "|---|---|",
                f"| Inserted | {_format_list(key_summary['inserted_examples'])} |",
                f"| Deleted | {_format_list(key_summary['deleted_examples'])} |",
                f"| Changed | {_format_list(key_summary['changed_examples'])} |",
                f"| Duplicate conflicts | {_format_list(key_summary['duplicate_examples'])} |",
                "",
            ]
        )

    lines.extend(
        [
            "## Recommended Next Checks",
            "",
            "- Confirm whether the row count decrease was expected.",
            "- Check whether an overwrite operation happened intentionally.",
            "- Review upstream filtering logic.",
            "- Investigate duplicate business keys before trusting one-to-one comparisons.",
            "- Compare affected records with source-system extracts where possible.",
            "",
        ]
    )

    return "\n".join(lines)
