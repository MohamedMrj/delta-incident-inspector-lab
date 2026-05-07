from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def build_markdown_report(
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
    generated_at: Optional[str] = None,
) -> str:
    if generated_at is None:
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


def _format_list(values: list) -> str:
    if not values:
        return "-"

    return ", ".join(str(value) for value in values)
