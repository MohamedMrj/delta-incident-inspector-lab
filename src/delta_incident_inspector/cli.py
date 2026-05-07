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
