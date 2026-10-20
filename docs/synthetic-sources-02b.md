# Slice 02B: observable source systems

Slice 02B projects the frozen 02A canonical world into five independent,
imperfect evidence systems: banking, GST, digital payments, financial
statements, and synthetic bureau snapshots. Each system uses canonical monthly
state plus its own capture, timing, noise, and missingness mechanisms. A source
is authoritative only for its own fact type; discrepancies are not fraud labels.

Every row retains the described period/date and an `available_at` timestamp.
Point-in-time consumers must use `available_at <= as_of`. Daily digital rows
have short availability lags, bank rows follow shortly after month end, GST and
bureau are later, and annual financial statements are latest. Missing rows,
`NULL` optional values, and zero-valued observations have different meanings:
an unavailable GST return is not a zero return, and a bureau no-hit is not a
score of zero.

Bank accounts are generated for every merchant, with additional accounts for
the 02A multi-account scenario. Detailed transactions are limited to the deep
cohort. Business receipts are the only eligible business-credit category;
internal transfers, loan disbursals, and capital infusions are excluded.
Merchant metrics aggregate all accounts. GST registrations similarly allocate
reported turnover across registrations instead of duplicating full turnover.

The approved foundation schema is intentionally reused. Its financial statement
table contains a compact P&L and total-assets/total-liabilities view, but no
equity or detailed balance-sheet line-item columns; therefore the generator
preserves the supported arithmetic identities and does not invent a migration
solely for synthetic convenience. Restatement/version behavior is represented
where the existing version fields support it.

The source data is for architecture validation, data-pipeline testing, source
reconciliation experiments, temporal-leakage testing, and later controlled
ML/RAG methodology work. It is not evidence of production validity for Indian
MSME lending. No applications, outcomes, decisions, fraud labels, documents,
embeddings, or external-source calls are generated.
