# Slice 02C: historical lending and evaluation evidence

02C creates a bounded historical underwriting environment over the frozen 02A
canonical world and 02B observable sources. Applications receive immutable
point-in-time snapshots using `available_at <= assessment_time`. The historical
synthetic lender accepts only that snapshot and a bounded policy context; it
does not receive future shocks, repayments, outcomes, or unrestricted merchant
history.

The clocks remain separate: application/assessment, decision/disbursement, and
outcome observation. Only approved applications produce historical loans,
repayment schedules, repayment transactions, and raw loan outcomes. Approval is
not a performance label. Only booked loans have performance observations, so
later modelling inherits selection effects from the historical lender.

Repayments are monthly and stochastic. Hidden pre-loan drivers and later source
state/shocks affect the probability of delay, but no deterministic default rule
is used. DPD can worsen, cure, or remain persistent. Loans without sufficient
follow-up are marked `CENSORED`, not good. No future rows mutate pre-application
source evidence.

Documents are rendered from structured facts. Ground-truth facts identify their
authority, and spans store exact character ranges in generated document text.
Golden questions include direct fact, temporal, source-comparison, and explicit
insufficient-evidence cases. Restricted-document metadata is assigned from the
trusted structured registry fields, never from document text.

Leakage matrix:

| Information | Historical decision | Future outcome analysis | Application-time feature |
|---|---:|---:|---:|
| Pre-application banking/GST/digital/financial/bureau | yes | yes | yes |
| Hidden 02A latent variables | generator only | yes | no |
| Post-application shocks | no | yes | no |
| Future repayments or bureau deterioration | no | outcome only | no |
| Prior-loan history observable before application T | yes | yes | yes |
| Prior-loan history after T | no | yes | no |

This synthetic historical lending data is for architecture validation,
leakage-control testing, pipeline development, and later controlled ML/RAG
methodology work. It is not evidence of actual Indian MSME default behavior,
real NBFC policy quality, or production credit-model validity.
