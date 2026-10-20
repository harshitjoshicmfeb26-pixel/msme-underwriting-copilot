# System design

The foundation separates authorization metadata (`authz`), operational merchant/application records (`core`), external source observations (`source`), historical lending (`lending`), trusted documents and policies (`docs`), evaluation truth (`truth`), and golden evaluation cases (`eval`). PostgreSQL constraints enforce basic temporal, money, enum-like, and relationship invariants. Application code will later add tenant authorization and richer cross-source validation.

Python enums improve readability while migrations use VARCHAR plus CHECK constraints, keeping schema evolution and interoperability simple.
