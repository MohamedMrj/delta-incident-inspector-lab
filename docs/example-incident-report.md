# Delta Incident Report

## Summary

- **Generated at:** `2026-01-01T00:00:00+00:00`
- **Table path:** `data/delta/customers`
- **Compared versions:** `2` → `4`

## Key Findings

- Suspicious row count drop detected: 8 → 4 (-50.00%).
- Duplicate key conflicts detected for 'customer_id'. One-to-one record comparison is unsafe for those keys.
- 5 key(s) disappeared between versions.
- 2 comparable key(s) changed values.

## Row Count Comparison

| Metric | Value |
|---|---:|
| From version | 2 |
| From row count | 8 |
| To version | 4 |
| To row count | 4 |
| Difference | -4 |
| Percent change | -50.00% |

## Schema Comparison

| Change Type | Columns |
|---|---|
| Added | - |
| Removed | - |
| Changed | - |

## Key-Level Diff

- **Key column:** `customer_id`

| Metric | Value |
|---|---:|
| From distinct non-null keys | 8 |
| To distinct non-null keys | 3 |
| From null key rows | 0 |
| To null key rows | 0 |
| Inserted keys | 0 |
| Deleted keys | 5 |
| Changed comparable keys | 2 |
| Unchanged comparable keys | 0 |
| Duplicate key conflicts | 1 |

### Example Keys

| Category | Examples |
|---|---|
| Inserted | - |
| Deleted | 4, 5, 6, 7, 8 |
| Changed | 1, 3 |
| Duplicate conflicts | 2 |

## Recommended Next Checks

- Confirm whether the row count decrease was expected.
- Check whether an overwrite operation happened intentionally.
- Review upstream filtering logic.
- Investigate duplicate business keys before trusting one-to-one comparisons.
- Compare affected records with source-system extracts where possible.
