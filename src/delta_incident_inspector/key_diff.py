from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KeyDiffSummary:
    from_null_key_rows: int
    to_null_key_rows: int
    from_distinct_keys: int
    to_distinct_keys: int
    inserted: list[Any]
    deleted: list[Any]
    changed: list[Any]
    unchanged: list[Any]
    duplicate_conflicts: list[Any]
    inserted_examples: list[Any]
    deleted_examples: list[Any]
    changed_examples: list[Any]
    duplicate_examples: list[Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_null_key_rows": self.from_null_key_rows,
            "to_null_key_rows": self.to_null_key_rows,
            "from_distinct_keys": self.from_distinct_keys,
            "to_distinct_keys": self.to_distinct_keys,
            "inserted": self.inserted,
            "deleted": self.deleted,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "duplicate_conflicts": self.duplicate_conflicts,
            "inserted_examples": self.inserted_examples,
            "deleted_examples": self.deleted_examples,
            "changed_examples": self.changed_examples,
            "duplicate_examples": self.duplicate_examples,
        }


def diff_by_key_dataframes(
    from_df: Any,
    to_df: Any,
    key: str,
    max_examples: int = 20,
) -> KeyDiffSummary:
    if key not in from_df.columns:
        raise ValueError(f"Key column '{key}' does not exist in from-version data")

    if key not in to_df.columns:
        raise ValueError(f"Key column '{key}' does not exist in to-version data")

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

    from_values = _align_values(from_unique, value_columns).reindex(comparable_keys)
    to_values = _align_values(to_unique, value_columns).reindex(comparable_keys)

    changed = []
    unchanged = []

    for key_value in comparable_keys:
        if from_values.loc[key_value].equals(to_values.loc[key_value]):
            unchanged.append(key_value)
        else:
            changed.append(key_value)

    return KeyDiffSummary(
        from_null_key_rows=from_null_key_rows,
        to_null_key_rows=to_null_key_rows,
        from_distinct_keys=len(from_keys),
        to_distinct_keys=len(to_keys),
        inserted=inserted,
        deleted=deleted,
        changed=changed,
        unchanged=unchanged,
        duplicate_conflicts=duplicate_conflicts,
        inserted_examples=inserted[:max_examples],
        deleted_examples=deleted[:max_examples],
        changed_examples=changed[:max_examples],
        duplicate_examples=duplicate_conflicts[:max_examples],
    )


def _align_values(df: Any, columns: list[str]) -> Any:
    aligned = df.copy()

    for column in columns:
        if column not in aligned.columns:
            aligned[column] = None

    return aligned[columns].astype("string").fillna("<NULL>")
