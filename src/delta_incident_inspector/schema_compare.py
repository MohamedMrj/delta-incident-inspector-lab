from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from deltalake import DeltaTable


@dataclass(frozen=True)
class SchemaComparison:
    added: list[str]
    removed: list[str]
    changed: list[str]
    from_fields: dict[str, dict[str, Any]]
    to_fields: dict[str, dict[str, Any]]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def _schema_to_dict(delta_table: DeltaTable) -> dict[str, Any]:
    schema_raw = delta_table.schema().json()

    if isinstance(schema_raw, str):
        return json.loads(schema_raw)

    return schema_raw


def _extract_fields(delta_table: DeltaTable) -> dict[str, dict[str, Any]]:
    schema = _schema_to_dict(delta_table)

    return {
        field["name"]: {
            "type": json.dumps(field["type"]),
            "nullable": field["nullable"],
        }
        for field in schema["fields"]
    }


def compare_schemas(
    from_table: DeltaTable,
    to_table: DeltaTable,
) -> SchemaComparison:
    from_fields = _extract_fields(from_table)
    to_fields = _extract_fields(to_table)

    added = sorted(set(to_fields) - set(from_fields))
    removed = sorted(set(from_fields) - set(to_fields))

    changed = []
    for column in sorted(set(from_fields) & set(to_fields)):
        if from_fields[column] != to_fields[column]:
            changed.append(column)

    return SchemaComparison(
        added=added,
        removed=removed,
        changed=changed,
        from_fields=from_fields,
        to_fields=to_fields,
    )
