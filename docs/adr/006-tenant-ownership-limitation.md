# Tenant ownership enforcement boundary

Phase 1 requires non-null tenant ownership on tenant-scoped tables and ordinary parent foreign keys. The current baseline does not use composite `(tenant_id, entity_id)` foreign keys, so PostgreSQL cannot independently prove that every child row's tenant matches its parent tenant. This slice documents the limitation and leaves production RLS and composite tenant-aware foreign keys for a later hardening change rather than changing the approved foundation design during validation.
