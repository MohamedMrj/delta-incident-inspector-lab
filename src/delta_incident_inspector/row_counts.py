from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from deltalake import DeltaTable


@dataclass(frozen=True)
class RowCountComparison:
    table_path: Path
    from_version: int
    to_version: int
    from_rows: int
    to_rows: int
    difference: int
    percent_change: Optional[float]

    @property
    def percent_change_text(self) -> str:
        if self.percent_change is None:
            return "n/a"

        return f"{self.percent_change:.2f}%"

    def is_suspicious_drop(self, warning_threshold_percent: float) -> bool:
        return self.percent_change is not None and self.percent_change <= -warning_threshold_percent


def compare_row_counts(
    table_path: Path,
    from_version: int,
    to_version: int,
) -> RowCountComparison:
    from_table = DeltaTable(str(table_path), version=from_version)
    to_table = DeltaTable(str(table_path), version=to_version)

    from_rows = from_table.to_pyarrow_table().num_rows
    to_rows = to_table.to_pyarrow_table().num_rows

    difference = to_rows - from_rows

    if from_rows == 0:
        percent_change = None
    else:
        percent_change = (difference / from_rows) * 100

    return RowCountComparison(
        table_path=table_path,
        from_version=from_version,
        to_version=to_version,
        from_rows=from_rows,
        to_rows=to_rows,
        difference=difference,
        percent_change=percent_change,
    )
