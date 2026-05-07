# Delta Incident Inspector Lab

A Dockerized data-engineering tool for investigating Delta Lake table incidents through both a **browser UI** and a **CLI**.

This project helps answer practical incident questions:

- What changed between Delta table versions?
- Did the schema change?
- Did the row count suddenly drop?
- Which business keys were inserted, deleted, changed, or duplicated?
- Can we generate a readable incident report?
- Can non-terminal users inspect incidents from a browser?

The project is designed as a realistic portfolio project for data engineers who work with Delta Lake, data quality checks, incident investigation, and production debugging.

---

## Why this project exists

Delta Lake gives data engineers versioned table history, but investigating an incident still requires careful manual work.

When a table breaks, you often need to quickly understand:

```text
Did someone overwrite the table?
Did the schema change?
Did important records disappear?
Did duplicate business keys appear?
Which version introduced the issue?
Can I generate a report to share with others?
```

Delta Incident Inspector provides a small but practical local lab for exploring those questions in an isolated Docker environment.

It supports two usage styles:

```text
Browser UI
  for users who want an easier visual workflow

CLI
  for engineers, automation, scripting, and reproducible investigations
```

---

## Features

- Browser-based Streamlit UI
- CLI for terminal-based investigation
- Delta table history inspection
- Row-count comparison between versions
- Schema comparison between versions
- Business-key-level diffing
- Duplicate key conflict detection
- Markdown incident report generation
- Reproducible sample incident data
- Dockerized development and runtime environment
- Automated linting and tests
- GitHub Actions CI

---

## Tech stack

- Python 3.11
- Docker
- Docker Compose
- Streamlit
- Delta Lake via `deltalake`
- PyArrow
- Pandas
- Typer CLI
- Rich terminal output
- Ruff
- Pytest
- GitHub Actions CI

---

## Project structure

```text
delta-incident-inspector-lab/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── architecture.md
│   └── example-incident-report.md
├── scripts/
│   └── generate_sample_delta_tables.py
├── src/
│   └── delta_incident_inspector/
│       ├── __init__.py
│       ├── cli.py
│       ├── key_diff.py
│       ├── reports.py
│       ├── row_counts.py
│       ├── schema_compare.py
│       └── ui.py
├── tests/
│   └── test_cli_smoke.py
├── Dockerfile
├── Makefile
├── compose.yaml
├── pyproject.toml
└── README.md
```

---

## Architecture

The project separates user interfaces from reusable investigation logic.

```text
Browser user
  │
  ▼
ui.py
  │
  ▼
shared core modules

Terminal user
  │
  ▼
cli.py
  │
  ▼
shared core modules
```

Core modules:

```text
row_counts.py
  Row count comparison between Delta versions

schema_compare.py
  Schema comparison between Delta versions

key_diff.py
  Business-key-level inserted/deleted/changed/duplicate detection

reports.py
  Markdown incident report rendering
```

This keeps the CLI and UI thin while keeping the core logic reusable and testable.

---

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/MohamedMrj/delta-incident-inspector-lab.git
cd delta-incident-inspector-lab
```

### 2. Build the Docker environment

```bash
make build
```

### 3. Generate sample Delta incident data

```bash
make seed
```

### 4. Start the browser UI

```bash
make ui
```

Then open:

```text
http://localhost:8501
```

Use the default values:

```text
Table path: data/delta/customers
From version: 2
To version: 4
Business key column: customer_id
```

---

## Browser UI

The browser UI is the easiest way to use the project.

Start it with:

```bash
make ui
```

Open:

```text
http://localhost:8501
```

The UI includes tabs for:

- History
- Row counts
- Schema
- Key diff
- Report

From the UI, users can:

- inspect Delta table history
- compare row counts
- compare schemas
- detect inserted/deleted/changed keys
- detect duplicate key conflicts
- generate and download a Markdown incident report

Stop the UI with:

```text
CTRL + C
```

---

## CLI usage

The CLI is still available for technical users, automation, and reproducible workflows.

### Environment check

```bash
docker compose run --rm app dii doctor
```

### Show Delta table history

```bash
docker compose run --rm app dii history data/delta/customers
```

### Show row count for one version

```bash
docker compose run --rm app dii row-count data/delta/customers --version 4
```

### Compare row counts between versions

```bash
docker compose run --rm app dii compare-row-counts data/delta/customers --from-version 2 --to-version 3
```

Example output:

```text
Row count comparison: v2 → v3

From row count: 8
To row count: 3
Difference: -5
Percent change: -62.50%

Warning: suspicious row count drop detected.
```

### Compare schemas between versions

```bash
docker compose run --rm app dii compare-schema data/delta/customers --from-version 0 --to-version 2
```

Example output:

```text
Schema comparison: v0 → v2

Added:
  email
```

### Compare records by business key

```bash
docker compose run --rm app dii diff-by-key data/delta/customers --from-version 2 --to-version 4 --key customer_id
```

This detects:

- inserted keys
- deleted keys
- changed comparable keys
- unchanged comparable keys
- duplicate key conflicts
- null key rows

### Generate an incident report

```bash
make report
```

This writes:

```text
docs/example-incident-report.md
```

---

## Sample incident timeline

The sample data generator creates a fake Delta table with multiple versions:

| Version | Scenario |
|---:|---|
| 0 | Initial healthy customer table |
| 1 | Normal append |
| 2 | Schema evolution: `email` column added |
| 3 | Suspicious overwrite with fewer rows |
| 4 | Duplicate business key introduced |

This lets the UI and CLI demonstrate realistic incident investigation behavior without requiring external data.

---

## Example report

A generated example report is included here:

```text
docs/example-incident-report.md
```

The report includes:

- summary
- key findings
- row count comparison
- schema comparison
- key-level diff
- recommended next checks

---

## Using your own Delta table

The table path must be visible inside the Docker container.

If your Delta table is inside the project directory, you can enter its path directly in the UI or CLI.

If your Delta table is outside the project directory, mount it in `compose.yaml`.

Example:

```yaml
services:
  app:
    volumes:
      - .:/workspace
      - /home/user/my-delta-tables:/data/delta-tables

  ui:
    volumes:
      - .:/workspace
      - /home/user/my-delta-tables:/data/delta-tables
```

Then use this path in the UI or CLI:

```text
/data/delta-tables/my-table
```

---

## Development workflow

### Build

```bash
make build
```

### Start the browser UI

```bash
make ui
```

### Start the browser UI in detached mode

```bash
make ui-detached
```

### Open shell inside the container

```bash
make shell
```

### Format code

```bash
make format
```

### Lint code

```bash
make lint
```

### Run tests

```bash
make test
```

### Clean generated data

```bash
make clean
```

---

## Why Docker?

The project is intentionally Dockerized so it can run without installing project dependencies globally on the host machine.

This is useful for:

- keeping the host PC clean
- creating a reproducible development environment
- making onboarding easier for other users
- demonstrating production-oriented engineering habits
- running both the CLI and UI in an isolated environment

---

## Testing and CI

The project includes smoke tests for the main workflows:

```bash
make test
```

Current test coverage includes:

- schema comparison
- key-diff behavior
- report generation

GitHub Actions runs linting and tests on pushes and pull requests.

The workflow is defined in:

```text
.github/workflows/ci.yml
```

---

## Current limitations

This is a local investigation lab, not yet a full production incident platform.

Current limitations:

- Designed mainly for local Delta tables
- Key-level diff loads data into memory using Pandas
- Large table support is not optimized yet
- No cloud object storage integration yet
- No Spark cluster execution yet
- Browser UI is intentionally simple
- User-provided table paths must be mounted into Docker

These limitations are intentional at this stage. The current goal is to provide a clean, understandable, reproducible Delta incident investigation tool.

---

## Roadmap

Planned improvements:

- Add JSON report output
- Add configurable warning thresholds
- Add better history timestamp formatting
- Add operation metrics from Delta history
- Add support for larger table comparisons
- Add optional MinIO/object storage lab
- Add Docker image build job in CI
- Add architecture diagram
- Add example GIF/demo recording
- Move duplicated report-finding logic into a shared incident summary module
- Improve UI styling and add clearer report previews

---

## Skills demonstrated

This project demonstrates:

- Docker-based development
- Python CLI design
- Browser-based data tool development with Streamlit
- Delta Lake version inspection
- Data quality investigation
- Schema comparison
- Business-key diffing
- Duplicate key conflict handling
- Report generation
- Clean modular refactoring
- Automated testing
- GitHub Actions CI
- Production-style project structure

---

## License

MIT
