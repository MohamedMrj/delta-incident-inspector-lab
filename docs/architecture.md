# Architecture

Delta Incident Inspector Lab is designed as a small, modular CLI tool for investigating Delta Lake table incidents.

The project intentionally keeps the architecture simple while still following production-oriented engineering habits:

- isolated Docker-based environment
- thin CLI layer
- reusable comparison modules
- generated sample incident data
- automated tests
- GitHub Actions CI

---

## High-level design

```text
User
  │
  ▼
CLI command
  │
  ▼
Delta table reader
  │
  ├── Row count comparison
  ├── Schema comparison
  ├── Key-level diff
  └── Markdown report generation
```

The CLI receives user input, loads the selected Delta table versions, calls the relevant comparison logic, and prints or writes the result.

---

## Module responsibilities

```text
src/delta_incident_inspector/
├── cli.py
├── row_counts.py
├── schema_compare.py
├── key_diff.py
└── reports.py
```

### `cli.py`

The CLI layer is responsible for:

- parsing command arguments
- validating table paths
- loading Delta table versions
- printing Rich terminal tables
- calling reusable logic from other modules

It should not contain large comparison algorithms.

### `row_counts.py`

Handles row-count comparison between two Delta table versions.

It returns a structured result containing:

- source version
- target version
- row counts
- row difference
- percent change
- suspicious-drop detection

This makes the row-count logic reusable from both CLI output and report generation.

### `schema_compare.py`

Handles schema comparison between two Delta table versions.

It detects:

- added columns
- removed columns
- changed columns

A changed column means its type or nullability changed.

### `key_diff.py`

Handles business-key-level comparison between two Delta table versions.

It detects:

- inserted keys
- deleted keys
- changed comparable keys
- unchanged comparable keys
- duplicate key conflicts
- null key rows

Duplicate key conflicts are treated carefully. If a key appears more than once in either version, the tool does not pretend it can safely perform a one-to-one comparison for that key.

This is intentional because duplicate business keys make record comparison ambiguous.

### `reports.py`

Builds Markdown incident reports.

The report includes:

- summary
- key findings
- row-count comparison
- schema comparison
- key-level diff
- recommended next checks

The report renderer is separated from the CLI so Markdown generation can be tested or reused without invoking command-line behavior.

---

## Data flow

A typical report command works like this:

```text
dii report
  │
  ├── Load Delta table at from-version
  ├── Load Delta table at to-version
  ├── Compare row counts
  ├── Compare schemas
  ├── Optionally compare by business key
  ├── Build findings
  └── Write Markdown report
```

Example:

```bash
docker compose run --rm app dii report data/delta/customers \
  --from-version 2 \
  --to-version 4 \
  --key customer_id \
  --output docs/example-incident-report.md
```

---

## Sample incident lab

The script:

```text
scripts/generate_sample_delta_tables.py
```

creates a local Delta table with multiple versions.

| Version | Scenario |
|---:|---|
| 0 | Initial healthy table |
| 1 | Normal append |
| 2 | Schema evolution |
| 3 | Suspicious overwrite with fewer rows |
| 4 | Duplicate business key introduced |

This makes the project reproducible. A reviewer can run the same commands and see the same type of incident investigation output.

---

## Why Docker is used

Docker is used to avoid installing project dependencies globally on the host machine.

Benefits:

- clean local environment
- reproducible setup
- easier onboarding
- safer experimentation
- consistent CLI behavior across machines

The project is especially suitable for Windows + WSL users because the development flow stays isolated inside Docker while the source code lives in the WSL filesystem.

---

## Why the CLI is modular

The first prototype started with most logic inside `cli.py`.

That worked, but it created a risk:

```text
cli.py becomes a large script that mixes UI, data loading, comparison logic, and reporting.
```

The project was refactored into modules so each part has one main responsibility.

This makes the project:

- easier to test
- easier to extend
- easier to explain
- easier to review
- closer to real production code

---

## Design tradeoffs

### Pandas is used for key-level diffing

The current key-diff implementation loads table versions into Pandas.

This is simple and good for a local investigation lab, but it is not optimized for very large tables.

For larger datasets, a future version could use:

- Polars
- DuckDB
- PySpark
- partition-aware comparison
- streaming/chunked comparison

### Local Delta tables only

The current project focuses on local Delta table paths.

Future versions could support:

- S3-compatible storage
- MinIO lab storage
- Azure Data Lake / OneLake paths
- configurable storage credentials

### No web UI

The project is currently CLI-first.

This is intentional. A CLI is faster to build, easier to test, and closer to many real data-engineering workflows.

A future web UI could be added later, but it should not replace the CLI.

---

## Testing strategy

The project currently includes smoke tests for the main workflows:

- schema comparison
- key-level diff
- Markdown report generation

The goal is not full exhaustive coverage yet. The goal is to protect the most important user flows while the project evolves.

---

## CI strategy

GitHub Actions runs:

- Ruff linting
- Pytest tests

This prevents broken code from being pushed unnoticed.

A future improvement could add a Docker build job to verify that the container image still builds successfully.

---

## Future architecture improvements

Potential future improvements:

- add JSON report output
- add structured logging
- add richer Delta history parsing
- add operation metrics from Delta transaction logs
- add MinIO object storage lab
- add larger-table comparison strategy
- add configurable incident rules
- add more focused unit tests for each module
- add Docker image build validation in CI
- add architecture diagram image

---

## Current architecture summary

```text
Docker / Compose
  provides isolated runtime

Typer CLI
  exposes user-facing commands

Delta Lake reader
  loads specific table versions

Core modules
  compare rows, schemas, and keys

Report module
  renders Markdown output

Tests + CI
  protect the main workflows
```

The project is intentionally small, but structured like a real engineering tool.
