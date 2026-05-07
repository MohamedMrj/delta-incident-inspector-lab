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
