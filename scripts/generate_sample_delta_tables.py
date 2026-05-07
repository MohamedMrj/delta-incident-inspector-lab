from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pyarrow as pa
from deltalake.writer import write_deltalake

TABLE_PATH = Path("data/delta/customers")


def write_version(df: pd.DataFrame, mode: str, schema_mode: str | None = None) -> None:
    arrow_table = pa.Table.from_pandas(df, preserve_index=False)

    kwargs = {
        "table_or_uri": str(TABLE_PATH),
        "data": arrow_table,
        "mode": mode,
    }

    if schema_mode is not None:
        kwargs["schema_mode"] = schema_mode

    write_deltalake(**kwargs)


def main() -> None:
    if TABLE_PATH.exists():
        shutil.rmtree(TABLE_PATH)

    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Version 0: normal initial table
    df_v0 = pd.DataFrame(
        [
            {"customer_id": 1, "name": "Alice", "status": "active"},
            {"customer_id": 2, "name": "Bob", "status": "active"},
            {"customer_id": 3, "name": "Charlie", "status": "inactive"},
            {"customer_id": 4, "name": "Diana", "status": "active"},
            {"customer_id": 5, "name": "Eve", "status": "active"},
        ]
    )
    write_version(df_v0, mode="overwrite")

    # Version 1: normal append
    df_v1 = pd.DataFrame(
        [
            {"customer_id": 6, "name": "Farah", "status": "active"},
            {"customer_id": 7, "name": "George", "status": "active"},
        ]
    )
    write_version(df_v1, mode="append")

    # Version 2: schema evolution, new email column
    df_v2 = pd.DataFrame(
        [
            {
                "customer_id": 8,
                "name": "Hana",
                "status": "active",
                "email": "hana@example.com",
            }
        ]
    )
    write_version(df_v2, mode="append", schema_mode="merge")

    # Version 3: suspicious overwrite with fewer rows
    df_v3 = pd.DataFrame(
        [
            {
                "customer_id": 1,
                "name": "Alice",
                "status": "active",
                "email": "alice@example.com",
            },
            {
                "customer_id": 2,
                "name": "Bob",
                "status": "unknown",
                "email": "bob@example.com",
            },
            {
                "customer_id": 3,
                "name": "Charlie",
                "status": "inactive",
                "email": "charlie@example.com",
            },
        ]
    )
    write_version(df_v3, mode="overwrite", schema_mode="overwrite")

    # Version 4: duplicate/business-key problem
    df_v4 = pd.DataFrame(
        [
            {
                "customer_id": 2,
                "name": "Bob Duplicate",
                "status": "active",
                "email": "bob.duplicate@example.com",
            }
        ]
    )
    write_version(df_v4, mode="append")

    print(f"Generated sample Delta table at: {TABLE_PATH}")


if __name__ == "__main__":
    main()
