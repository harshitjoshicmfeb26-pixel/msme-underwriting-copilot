# Data dictionary

The migration is the authoritative definition of the Phase 1 tables. Tenant-scoped operational records carry a non-null `tenant_id` to remain ready for future row-level security. `available_at` means the earliest legitimate knowledge time, not ingestion time. Amounts are `NUMERIC(18,2)` and are handled as `Decimal` in Python.

The synthetic bureau rank is a simplified synthetic field only; it does not reproduce any proprietary bureau score. `lending.loan_outcomes` stores historical future outcomes and is not a model-prediction table. `truth` tables are evaluation truth, not operational business records.
