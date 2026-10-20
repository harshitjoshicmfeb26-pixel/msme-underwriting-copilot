# India MSME Credit Intelligence & Underwriting Copilot

This project will become a human-in-the-loop decision-support platform for MSME credit analysts. Phase 1, Foundation Slice 1 establishes the production-oriented Python/PostgreSQL data foundation: tenant-aware schemas, source and lending records, trusted document metadata, evaluation truth, deterministic constraints, typed settings, and migrations.

RAG, ML, embeddings, LangGraph, APIs, cloud integration, authentication, and RLS policies are deliberately absent. They are later slices, not placeholders in this foundation.

## Local setup

Use Python 3.11, install the package and development tools, then copy `.env.example` to `.env`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
pytest
ruff check .
mypy src
```

For PostgreSQL integration tests, configure the database URL explicitly:

```powershell
$env:TEST_DATABASE_URL = "<your PostgreSQL connection URL>"
pytest -m integration
```

The integration fixture performs a clean `downgrade base` followed by `upgrade head` before the suite and removes the schemas afterward. To reset a local Compose database, stop the service and remove only its named volume:

```powershell
docker compose down
docker volume rm msme-underwriting-copilot_postgres_data
docker compose up -d postgres
```

`available_at` is the earliest timestamp at which a record could legitimately have been known to the system. All such columns use timezone-aware timestamps and PostgreSQL `TIMESTAMPTZ`. Money uses Python `Decimal` and PostgreSQL `NUMERIC(18,2)`; binary floating point is not accepted by the money helper.

## Migration usage

`alembic upgrade head` creates the seven logical schemas and the Phase 1 tables. `alembic downgrade base` removes the foundation schemas. The first migration is intentionally kept atomic because every later schema contains cross-schema foreign keys; the conceptual schema sections remain explicit inside the migration.

## Tests and quality

Run `pytest` against PostgreSQL for database integration coverage. `ruff check .`, `mypy src`, `git diff --check`, and the Alembic upgrade/downgrade cycle are the documented validation commands.

The current schema uses separate tenant IDs and ordinary foreign keys. It does not yet enforce cross-table tenant equality at database level. Application validation covers current use, while composite tenant-aware foreign keys are a later hardening option.

## Slice 02A synthetic world

`python -m msme_copilot.synthetic.generate` creates the deterministic 6,000-merchant, 24-month canonical world using seed `314159`. It writes hidden latent state and monthly state to ignored JSONL artifacts under `data/synthetic/`. Add `--persist` to write only canonical merchants to PostgreSQL; no GST, banking, bureau, financial-statement, payment, document, policy, or loan-outcome rows are generated.

## Phase 1 status

Phase 1 is complete and frozen. It includes the PostgreSQL foundation, deterministic synthetic MSME world, Banking/GST/Digital/Financial/Bureau source evidence, historically ordered lending and outcomes, and a source-grounded document, truth, and evaluation corpus. The generators are reproducible from their documented seeds and are covered by unit, PostgreSQL integration, Ruff, mypy, and Python compilation checks. The data is synthetic and is not evidence of production lending performance. ML, RAG, embeddings, APIs, cloud integration, authentication, and RLS remain outside Phase 1.
