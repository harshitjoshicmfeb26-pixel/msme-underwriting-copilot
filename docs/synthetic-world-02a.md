# Slice 02A: canonical merchant world

Slice 02A generates a hidden synthetic reality: 6,000 deterministic merchants, 200 complex-cohort merchants, 40 deep-cohort merchants, and 24 monthly latent business states per merchant. The default seed is `314159`.

Merchants use ten archetypes with noisy, correlated latent variables. Scale influences operating complexity; digital adoption reduces cash dependence; repayment discipline contributes to bureau quality; stability reduces volatility; and working-capital intensity affects liquidity. These are generator causes, not customer-visible underwriting features or fraud labels.

Monthly revenue combines scale, gradual growth, merchant-specific seasonal phase/amplitude, noisy realization, and sparse deterministic shocks. All dates are valid relative to the 24-month reference window and revenue is non-negative.

Only canonical merchants are persisted to `core.merchants` with `--persist`. Latent variables, scenario tags, and monthly state remain versionable synthetic JSONL artifacts so the production schema is not polluted by generator internals. No source-system observations are generated in 02A.

Synthetic data supports architecture validation, pipeline demonstrations, controlled experiments, and evaluation-harness development. It cannot establish that a model trained on it is valid for real-world Indian MSME lending; real-world validity requires representative approved data, leakage controls, calibration, fairness analysis, and production monitoring.
